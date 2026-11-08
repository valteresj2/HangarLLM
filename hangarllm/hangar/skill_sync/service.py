"""Skills Hub Git Sync orchestration: lock, fetch commit, validate, apply or stage for approval, record."""

import asyncio
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Final

import httpx
from pydantic import SecretStr

from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.skill_sync.apply import SyncTarget, access_group_name, apply_discovery
from hangarllm.hangar.skill_sync.discovery import DiscoveryFailure, discover_skills
from hangarllm.hangar.skill_sync.github import (
    GitHubClient,
    GitHubError,
    HeadCommit,
    NotModified,
    commit_url,
    repository_url,
)
from hangarllm.hangar.skill_sync.hub import PrismaHub, SkillPublishError
from hangarllm.hangar.skill_sync.types import (
    GitConnection,
    GitSource,
    GitSync,
    SourceStatus,
    SyncReport,
    SyncStatus,
    SyncTrigger,
)

if TYPE_CHECKING:
    from prisma.models import HangarLLM_SkillGitSource, HangarLLM_SkillGitSync

    from hangarllm.proxy.utils import PrismaClient as Prisma

LOCK_SECONDS: Final = 600
_etags: dict[str, tuple[str, str]] = {}  # mutable-ok: per-process ETag cache {source_id: (etag, sha)}


def sources(prisma: "Prisma"):
    return prisma.writer_db.hangarllm_skillgitsource


def syncs(prisma: "Prisma"):
    return prisma.writer_db.hangarllm_skillgitsync


class SyncBusy(Exception):
    pass


class SourceNotFound(Exception):
    pass


def http_client() -> httpx.AsyncClient:
    from hangarllm.llms.custom_httpx.http_handler import get_async_httpx_client

    return get_async_httpx_client(llm_provider="hangar_skill_sync").client


def base_url(request_base_url: str | None = None) -> str:
    from hangarllm.proxy.utils import get_proxy_base_url

    return (get_proxy_base_url() or request_base_url or "http://localhost:4000").rstrip("/")


def webhook_url(source_id: str, request_base_url: str | None = None) -> str:
    return f"{base_url(request_base_url)}/skill-hub/git-sources/{source_id}/webhook"


def new_webhook_secret() -> str:
    return secrets.token_hex(32)


def encrypt(value: str) -> str:
    from hangarllm.proxy.common_utils.encrypt_decrypt_utils import encrypt_value_helper

    return encrypt_value_helper(value)


def decrypt(value: str | None, field: str) -> str | None:
    from hangarllm.proxy.common_utils.encrypt_decrypt_utils import decrypt_value_helper

    return None if value is None else decrypt_value_helper(value, key=field, exception_type="error")


def credentials_blob(connection: GitConnection) -> str | None:
    secret: Final = {
        **({"token": connection.token.get_secret_value()} if connection.token is not None else {}),
        **({"private_key": connection.private_key.get_secret_value()} if connection.private_key is not None else {}),
    }
    return encrypt(json.dumps(secret)) if secret else None


def connection_of(row: "HangarLLM_SkillGitSource") -> GitConnection:
    raw: Final = decrypt(row.credentials, "skill_git_credentials")
    secret: Final = json.loads(raw) if raw else {}
    return GitConnection.model_validate(
        {
            "auth_type": row.auth_type,
            "api_base_url": row.api_base_url,
            "token": SecretStr(secret["token"]) if "token" in secret else None,
            "app_id": row.app_id,
            "installation_id": row.installation_id,
            "private_key": SecretStr(secret["private_key"]) if "private_key" in secret else None,
        }
    )


def to_api_source(row: "HangarLLM_SkillGitSource", request_base_url: str | None = None) -> GitSource:
    return GitSource.model_validate(
        {
            "source_id": row.source_id,
            "name": row.name,
            "api_base_url": row.api_base_url,
            "owner": row.owner,
            "repository": row.repository,
            "repository_url": repository_url(row.api_base_url, row.owner, row.repository),
            "branch": row.branch,
            "skills_path": row.skills_path,
            "auth_type": row.auth_type,
            "app_id": row.app_id,
            "installation_id": row.installation_id,
            "has_credentials": row.credentials is not None,
            "scope": row.scope,
            "access_group_id": row.access_group_id,
            "access_group_name": access_group_name(row.owner, row.repository),
            "publish_mode": row.publish_mode,
            "remove_policy": row.remove_policy,
            "auto_sync": row.auto_sync,
            "poll_interval_seconds": row.poll_interval_seconds,
            "status": row.status,
            "status_message": row.status_message,
            "last_seen_sha": row.last_seen_sha,
            "applied_sha": row.applied_sha,
            "last_checked_at": row.last_checked_at,
            "last_synced_at": row.last_synced_at,
            "managed_skills": tuple(row.managed_skills or ()),
            "quarantined_skills": tuple(row.quarantined_skills or ()),
            "webhook_url": webhook_url(row.source_id, request_base_url),
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
        }
    )


def to_api_sync(row: "HangarLLM_SkillGitSync", source: "HangarLLM_SkillGitSource") -> GitSync:
    return GitSync.model_validate(
        {
            "sync_id": row.sync_id,
            "source_id": row.source_id,
            "commit_sha": row.commit_sha,
            "commit_url": commit_url(source.api_base_url, source.owner, source.repository, row.commit_sha)
            if row.commit_sha
            else None,
            "trigger": row.trigger,
            "status": row.status,
            "report": SyncReport.model_validate_json(row.report_json or '{"commit_sha": null, "applied": false}'),
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "triggered_by": row.triggered_by,
        }
    )


async def _lock(prisma: "Prisma", source_id: str) -> bool:
    now: Final = datetime.now(timezone.utc)
    acquired: Final = await sources(prisma).update_many(
        where={"source_id": source_id, "OR": [{"sync_lock_until": None}, {"sync_lock_until": {"lt": now}}]},
        data={"sync_lock_until": now + timedelta(seconds=LOCK_SECONDS)},
    )
    return acquired == 1


async def _unlock(prisma: "Prisma", source_id: str) -> None:
    await sources(prisma).update(where={"source_id": source_id}, data={"sync_lock_until": None})


def _failed(sha: str | None, message: str) -> SyncReport:
    return SyncReport(commit_sha=sha, applied=False, error=message)


def _statuses(report: SyncReport, *, staged: bool, changed: bool) -> tuple[SyncStatus, SourceStatus, str | None]:
    if report.error is not None:
        return "failed", "failed", report.error
    quarantined: Final = report.summary.quarantined
    has_errors: Final = quarantined > 0 or any(i.severity == "error" for i in report.issues)
    has_warnings: Final = has_errors or any(
        i.severity == "warning" for i in (*report.issues, *(i for s in report.skills for i in s.issues))
    )
    message: Final = (
        f"{quarantined} skill(s) quarantined; review the latest sync report" if quarantined else None
    ) or ("Some files need attention; review the latest sync report" if has_warnings else None)
    if staged and changed:
        return "pending_approval", "pending_approval", "A new commit is waiting for admin approval"
    if not changed:
        return "no_changes", ("warnings" if has_warnings else "healthy"), message
    return (
        ("applied_with_warnings" if has_warnings else "applied"),
        ("warnings" if has_warnings else "healthy"),
        message,
    )


async def run_sync(
    prisma: "Prisma",
    source_id: str,
    trigger: SyncTrigger,
    actor: str | None,
    *,
    sha: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> GitSync:
    row: Final = await sources(prisma).find_unique(where={"source_id": source_id})
    if row is None:
        raise SourceNotFound(source_id)
    if not await _lock(prisma, source_id):
        raise SyncBusy(source_id)
    try:
        return await _run_locked(prisma, row, trigger, actor, sha, client or http_client())
    finally:
        await _unlock(prisma, source_id)


async def _resolve_sha(gh: GitHubClient, row: "HangarLLM_SkillGitSource", sha: str | None) -> str | GitHubError:
    if sha is not None:
        return sha
    head: Final = await gh.head_commit(row.owner, row.repository, row.branch)
    if isinstance(head, NotModified):
        return GitHubError(502, "GitHub returned no commit for the branch")
    return head if isinstance(head, GitHubError) else head.sha


async def _run_locked(
    prisma: "Prisma",
    row: "HangarLLM_SkillGitSource",
    trigger: SyncTrigger,
    actor: str | None,
    requested_sha: str | None,
    client: httpx.AsyncClient,
) -> GitSync:
    started: Final = datetime.now(timezone.utc)
    await sources(prisma).update(where={"source_id": row.source_id}, data={"status": "syncing"})
    gh: Final = GitHubClient(connection_of(row), client)
    staged: Final = row.publish_mode == "approval" and trigger not in ("approval", "rollback")
    sha: Final = await _resolve_sha(gh, row, requested_sha)
    outcome: Final = await _evaluate(prisma, row, gh, sha, actor, apply=not staged)
    report, managed, quarantined, group_id, changed = outcome
    sync_status, source_status, message = _statuses(report, staged=staged, changed=changed)
    commit: Final = sha if isinstance(sha, str) else None
    if sync_status == "pending_approval":
        await syncs(prisma).update_many(
            where={"source_id": row.source_id, "status": "pending_approval"}, data={"status": "superseded"}
        )
    created: Final = await syncs(prisma).create(
        data={
            "source_id": row.source_id,
            "commit_sha": commit,
            "trigger": trigger,
            "status": sync_status,
            "report_json": report.model_dump_json(),
            "started_at": started,
            "finished_at": datetime.now(timezone.utc),
            "triggered_by": actor,
        }
    )
    applied: Final = sync_status in ("applied", "applied_with_warnings", "no_changes") and report.applied
    updated: Final = await sources(prisma).update(
        where={"source_id": row.source_id},
        data={
            "status": source_status,
            "status_message": message,
            "last_seen_sha": commit or row.last_seen_sha,
            "last_checked_at": datetime.now(timezone.utc),
            **(
                {
                    "applied_sha": commit,
                    "last_synced_at": datetime.now(timezone.utc),
                    "managed_skills": list(managed),
                    "quarantined_skills": list(quarantined),
                    **({"access_group_id": group_id} if group_id else {}),
                }
                if applied
                else {}
            ),
        },
    )
    result: Final = to_api_sync(created, updated or row)
    await notify(updated or row, result)
    return result


async def _evaluate(
    prisma: "Prisma",
    row: "HangarLLM_SkillGitSource",
    gh: GitHubClient,
    sha: str | GitHubError,
    actor: str | None,
    *,
    apply: bool,
) -> tuple[SyncReport, tuple[str, ...], tuple[str, ...], str | None, bool]:
    unchanged: Final = (tuple(row.managed_skills or ()), tuple(row.quarantined_skills or ()), None, False)
    if isinstance(sha, GitHubError):
        return (_failed(None, sha.message), *unchanged)
    archive: Final = await gh.download_archive(row.owner, row.repository, sha)
    if isinstance(archive, GitHubError):
        return (_failed(sha, archive.message), *unchanged)
    discovery: Final = await asyncio.to_thread(discover_skills, archive, row.skills_path)
    if isinstance(discovery, DiscoveryFailure):
        return (_failed(sha, discovery.message), *unchanged)
    repo: Final = f"{row.owner}/{row.repository}"
    hub: Final = PrismaHub(
        prisma, base_url=base_url(), actor=actor or f"git-sync:{repo}", reviewer=f"github:{repo}@{sha[:12]}"
    )
    target: Final = SyncTarget(
        owner=row.owner,
        repository=row.repository,
        commit_sha=sha,
        origin_base=repository_url(row.api_base_url, row.owner, row.repository),
        scope="all_keys" if row.scope == "all_keys" else "access_group",
        remove_policy="keep" if row.remove_policy == "keep" else "unpublish",
        managed_skills=frozenset(row.managed_skills or ()),
    )
    try:
        result: Final = await apply_discovery(discovery, target, hub, apply=apply)
    except SkillPublishError as error:
        return (_failed(sha, f"Publishing failed: {error}"), *unchanged)
    return result.report, result.managed_skills, result.quarantined_skills, result.access_group_id, result.changed


async def notify(row: "HangarLLM_SkillGitSource", sync: GitSync) -> None:
    if sync.status not in ("failed", "pending_approval") and sync.report.summary.quarantined == 0:
        return
    from hangarllm.proxy.proxy_server import proxy_logging_obj
    from hangarllm.types.integrations.slack_alerting import AlertType

    detail: Final = sync.report.error or (
        "waiting for approval"
        if sync.status == "pending_approval"
        else f"{sync.report.summary.quarantined} skill(s) quarantined"
    )
    message: Final = (
        f"Skills Hub Git Sync `{row.name}` ({row.owner}/{row.repository}@{row.branch}) "
        f"commit {(sync.commit_sha or '?')[:7]}: {detail}. Open Skills > GitHub Sync to review."
    )
    try:
        await proxy_logging_obj.alerting_handler(
            message=message,
            level="High" if sync.status == "failed" else "Medium",
            alert_type=AlertType.skill_sync_alerts,
        )
    except Exception as error:  # noqa: BLE001  # alert delivery must never fail a sync
        verbose_proxy_logger.warning("Skill sync alert could not be delivered: %s", error)


def _due(row: "HangarLLM_SkillGitSource", now: datetime) -> bool:
    return row.last_checked_at is None or row.last_checked_at + timedelta(seconds=row.poll_interval_seconds) <= now


async def poll_sources(prisma: "Prisma", client: httpx.AsyncClient | None = None) -> None:
    now: Final = datetime.now(timezone.utc)
    rows: Final = await sources(prisma).find_many(where={"auto_sync": True})
    http: Final = client or http_client()
    for row in (r for r in rows if _due(r, now)):
        try:
            await _poll_one(prisma, row, http)
        except SyncBusy:
            continue
        except Exception as error:  # noqa: BLE001  # one broken source must not stop polling the others
            verbose_proxy_logger.warning("Skill sync poll failed for %s: %s", row.name, error)


async def _poll_one(prisma: "Prisma", row: "HangarLLM_SkillGitSource", client: httpx.AsyncClient) -> None:
    cached: Final = _etags.get(row.source_id)
    head: Final = await GitHubClient(connection_of(row), client).head_commit(
        row.owner, row.repository, row.branch, etag=cached[0] if cached else None
    )
    sha: Final = (
        cached[1] if isinstance(head, NotModified) and cached else head.sha if isinstance(head, HeadCommit) else None
    )
    if isinstance(head, HeadCommit) and head.etag:
        _etags[row.source_id] = (head.etag, head.sha)
    if sha is None:
        await sources(prisma).update(
            where={"source_id": row.source_id},
            data={
                "last_checked_at": datetime.now(timezone.utc),
                **({"status": "failed", "status_message": head.message} if isinstance(head, GitHubError) else {}),
            },
        )
        return
    already_seen: Final = row.status != "failed" and sha in (row.applied_sha, row.last_seen_sha)
    if already_seen:
        await sources(prisma).update(
            where={"source_id": row.source_id}, data={"last_checked_at": datetime.now(timezone.utc)}
        )
        return
    await run_sync(prisma, row.source_id, "poll", None, sha=sha, client=client)
