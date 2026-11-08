"""HTTP API for Skills Hub Git Sync. Admin-only, except the HMAC-verified GitHub webhook."""

import asyncio
import hashlib
import hmac
import json
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.proxy._auth import require_db, require_proxy_admin
from hangarllm.hangar.skill_sync import service
from hangarllm.hangar.skill_sync.github import GitHubClient, GitHubError
from hangarllm.hangar.skill_sync.hub import PrismaHub
from hangarllm.hangar.skill_sync.types import (
    BranchList,
    BranchQuery,
    GitConnection,
    GitSource,
    GitSourceCreate,
    GitSourceCreated,
    GitSourceList,
    GitSourceUpdate,
    GitSync,
    GitSyncList,
    RepositoryList,
    SyncTrigger,
    WebhookAck,
    WebhookSetup,
)
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth

router: Final = APIRouter(prefix="/skill-hub/git-sources", tags=["Skills Hub Git Sync"])
_background: set[asyncio.Task[None]] = set()  # mutable-ok: keeps webhook-triggered syncs alive until done
_ROLLBACK_OK: Final = frozenset({"applied", "applied_with_warnings", "no_changes"})


def _admin(caller: UserAPIKeyAuth) -> str:
    require_proxy_admin(caller)
    return caller.user_id or "proxy-admin"


def _raise(error: GitHubError) -> HTTPException:
    return HTTPException(status_code=400 if error.status < 500 else 502, detail={"error": error.message})


async def _row(source_id: str):
    row: Final = await service.sources(require_db()).find_unique(where={"source_id": source_id})
    if row is None:
        raise HTTPException(404, {"error": "Git source not found"})
    return row


async def _run(source_id: str, trigger: SyncTrigger, actor: str | None, sha: str | None = None) -> GitSync:
    try:
        return await service.run_sync(require_db(), source_id, trigger, actor, sha=sha)
    except service.SyncBusy:
        raise HTTPException(409, {"error": "A sync for this repository is already running. Try again shortly."})
    except service.SourceNotFound:
        raise HTTPException(404, {"error": "Git source not found"})


@router.get("", response_model=GitSourceList)
async def list_sources(
    request: Request, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSourceList:
    _admin(caller)
    rows: Final = await service.sources(require_db()).find_many(order={"name": "asc"})
    return GitSourceList(sources=tuple(service.to_api_source(r, str(request.base_url)) for r in rows))


@router.post("/discover/repositories", response_model=RepositoryList)
async def discover_repositories(
    connection: GitConnection, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> RepositoryList:
    _admin(caller)
    result: Final = await GitHubClient(connection, service.http_client()).list_repositories()
    if isinstance(result, GitHubError):
        raise _raise(result)
    return result


@router.post("/discover/branches", response_model=BranchList)
async def discover_branches(
    query: BranchQuery, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> BranchList:
    _admin(caller)
    result: Final = await GitHubClient(query.connection, service.http_client()).list_branches(
        query.owner, query.repository
    )
    if isinstance(result, GitHubError):
        raise _raise(result)
    return result


@router.post("", response_model=GitSourceCreated)
async def create_source(
    request: Request, body: GitSourceCreate, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSourceCreated:
    actor: Final = _admin(caller)
    prisma: Final = require_db()
    head: Final = await GitHubClient(body.connection, service.http_client()).head_commit(
        body.owner, body.repository, body.branch
    )
    if isinstance(head, GitHubError):
        raise _raise(head)
    if await service.sources(prisma).find_unique(where={"name": body.name}) is not None:
        raise HTTPException(409, {"error": f"A Git source named '{body.name}' already exists"})
    secret: Final = service.new_webhook_secret()
    row: Final = await service.sources(prisma).create(
        data={
            "name": body.name,
            "api_base_url": body.connection.api_base_url,
            "owner": body.owner,
            "repository": body.repository,
            "branch": body.branch,
            "skills_path": body.skills_path,
            "auth_type": body.connection.auth_type,
            "credentials": service.credentials_blob(body.connection),
            "app_id": body.connection.app_id,
            "installation_id": body.connection.installation_id,
            "scope": body.scope,
            "publish_mode": body.publish_mode,
            "remove_policy": body.remove_policy,
            "auto_sync": body.auto_sync,
            "poll_interval_seconds": body.poll_interval_seconds,
            "webhook_secret": service.encrypt(secret),
            "created_by": actor,
            "updated_by": actor,
        }
    )
    sync: Final = await _run(row.source_id, "create", actor) if body.sync_now else None
    fresh: Final = await _row(row.source_id)
    return GitSourceCreated(
        source=service.to_api_source(fresh, str(request.base_url)),
        webhook=WebhookSetup(url=service.webhook_url(row.source_id, str(request.base_url)), secret=secret),
        sync=sync,
    )


@router.get("/{source_id}", response_model=GitSource)
async def get_source(
    request: Request, source_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSource:
    _admin(caller)
    return service.to_api_source(await _row(source_id), str(request.base_url))


def _connection_update(row, connection: GitConnection | None) -> dict[str, object]:
    if connection is None:
        return {}
    has_secret: Final = connection.token is not None or connection.private_key is not None
    keep_secret: Final = not has_secret and connection.auth_type == row.auth_type
    return {
        "auth_type": connection.auth_type,
        "api_base_url": connection.api_base_url,
        "app_id": connection.app_id,
        "installation_id": connection.installation_id,
        **({} if keep_secret else {"credentials": service.credentials_blob(connection)}),
    }


@router.patch("/{source_id}", response_model=GitSource)
async def update_source(
    request: Request,
    source_id: str,
    body: GitSourceUpdate,
    caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> GitSource:
    actor: Final = _admin(caller)
    row: Final = await _row(source_id)
    settings: Final = body.model_dump(exclude_none=True, exclude={"connection"})
    retarget: Final = any(k in settings and settings[k] != getattr(row, k) for k in ("branch", "skills_path"))
    updated: Final = await service.sources(require_db()).update(
        where={"source_id": source_id},
        data={
            **settings,
            **_connection_update(row, body.connection),
            **({"last_seen_sha": None} if retarget else {}),
            **({"status_message": None} if body.auto_sync else {}),
            "updated_by": actor,
        },
    )
    return service.to_api_source(updated or row, str(request.base_url))


@router.delete("/{source_id}", status_code=204, response_class=Response)
async def delete_source(
    source_id: str,
    caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
    unpublish_skills: Annotated[bool, Query()] = False,
) -> Response:
    actor: Final = _admin(caller)
    prisma: Final = require_db()
    row: Final = await _row(source_id)
    if unpublish_skills:
        hub: Final = PrismaHub(prisma, base_url=service.base_url(), actor=actor, reviewer=actor)
        for name in row.managed_skills or ():
            await hub.set_enabled(name, False)
        await hub.sync_access_group(f"git:{row.owner}/{row.repository}", ())
    await service.syncs(prisma).delete_many(where={"source_id": source_id})
    await service.sources(prisma).delete(where={"source_id": source_id})
    return Response(status_code=204)


@router.post("/{source_id}/sync", response_model=GitSync)
async def sync_now(source_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]) -> GitSync:
    return await _run(source_id, "manual", _admin(caller))


@router.get("/{source_id}/syncs", response_model=GitSyncList)
async def list_syncs(
    source_id: str,
    caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GitSyncList:
    _admin(caller)
    row: Final = await _row(source_id)
    rows: Final = await service.syncs(require_db()).find_many(
        where={"source_id": source_id}, order={"started_at": "desc"}, take=limit
    )
    return GitSyncList(syncs=tuple(service.to_api_sync(r, row) for r in rows))


async def _sync_row(source_id: str, sync_id: str):
    found: Final = await service.syncs(require_db()).find_first(where={"sync_id": sync_id, "source_id": source_id})
    if found is None:
        raise HTTPException(404, {"error": "Sync not found"})
    return found


@router.post("/{source_id}/syncs/{sync_id}/approve", response_model=GitSync)
async def approve_sync(
    source_id: str, sync_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSync:
    actor: Final = _admin(caller)
    pending: Final = await _sync_row(source_id, sync_id)
    if pending.status != "pending_approval" or pending.commit_sha is None:
        raise HTTPException(409, {"error": "Only syncs waiting for approval can be approved"})
    result: Final = await _run(source_id, "approval", actor, sha=pending.commit_sha)
    await service.syncs(require_db()).update(where={"sync_id": sync_id}, data={"status": "superseded"})
    return result


@router.post("/{source_id}/syncs/{sync_id}/reject", response_model=GitSync)
async def reject_sync(
    source_id: str, sync_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSync:
    actor: Final = _admin(caller)
    prisma: Final = require_db()
    pending: Final = await _sync_row(source_id, sync_id)
    if pending.status != "pending_approval":
        raise HTTPException(409, {"error": "Only syncs waiting for approval can be rejected"})
    rejected: Final = await service.syncs(prisma).update(
        where={"sync_id": sync_id}, data={"status": "rejected", "triggered_by": actor}
    )
    source: Final = await service.sources(prisma).update(
        where={"source_id": source_id},
        data={
            "status": "healthy" if pending.commit_sha else "failed",
            "status_message": f"Commit {(pending.commit_sha or '')[:7]} was rejected by {actor}",
        },
    )
    return service.to_api_sync(rejected or pending, source or await _row(source_id))


@router.post("/{source_id}/syncs/{sync_id}/rollback", response_model=GitSync)
async def rollback_sync(
    source_id: str, sync_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> GitSync:
    actor: Final = _admin(caller)
    target: Final = await _sync_row(source_id, sync_id)
    if target.status not in _ROLLBACK_OK or target.commit_sha is None:
        raise HTTPException(409, {"error": "Only applied syncs can be rolled back to"})
    result: Final = await _run(source_id, "rollback", actor, sha=target.commit_sha)
    await service.sources(require_db()).update(
        where={"source_id": source_id},
        data={
            "auto_sync": False,
            "status_message": f"Rolled back to {target.commit_sha[:7]}. Auto sync is paused; "
            "turn it back on to follow the branch again.",
        },
    )
    return result


@router.post("/{source_id}/webhook-secret/rotate", response_model=WebhookSetup)
async def rotate_webhook_secret(
    request: Request, source_id: str, caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)]
) -> WebhookSetup:
    actor: Final = _admin(caller)
    await _row(source_id)
    secret: Final = service.new_webhook_secret()
    await service.sources(require_db()).update(
        where={"source_id": source_id}, data={"webhook_secret": service.encrypt(secret), "updated_by": actor}
    )
    return WebhookSetup(url=service.webhook_url(source_id, str(request.base_url)), secret=secret)


def valid_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected: Final = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def _schedule(source_id: str, sha: str) -> None:
    async def _job() -> None:
        try:
            await service.run_sync(require_db(), source_id, "webhook", "github-webhook", sha=sha)
        except service.SyncBusy:
            verbose_proxy_logger.info(
                "Skill sync for %s already running; webhook commit %s left to polling", source_id, sha
            )
        except Exception as error:  # noqa: BLE001  # background task must log, not crash the event loop
            verbose_proxy_logger.warning("Webhook-triggered skill sync failed for %s: %s", source_id, error)

    task: Final = asyncio.create_task(_job())
    _background.add(task)
    task.add_done_callback(_background.discard)


@router.post("/{source_id}/webhook", response_model=WebhookAck)
async def github_webhook(source_id: str, request: Request) -> WebhookAck:
    row: Final = await service.sources(require_db()).find_unique(where={"source_id": source_id})
    body: Final = await request.body()
    secret: Final = service.decrypt(row.webhook_secret, "skill_git_webhook_secret") if row is not None else None
    if row is None or secret is None or not valid_signature(secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, {"error": "Invalid webhook signature"})
    event: Final = request.headers.get("x-github-event", "")
    if event == "ping":
        return WebhookAck(accepted=True, reason="pong")
    if event != "push":
        return WebhookAck(accepted=False, reason=f"Ignored event '{event}'")
    try:
        payload: Final = json.loads(body)
    except ValueError:
        raise HTTPException(400, {"error": "Webhook body is not JSON"})
    ref: Final = payload.get("ref") if isinstance(payload, dict) else None
    after: Final = payload.get("after") if isinstance(payload, dict) else None
    if ref != f"refs/heads/{row.branch}":
        return WebhookAck(accepted=False, reason=f"Push to {ref} ignored; this source follows {row.branch}")
    if not isinstance(after, str) or len(after) != 40 or set(after) == {"0"}:
        return WebhookAck(accepted=False, reason="Push without a new commit (branch deleted?)")
    if not row.auto_sync:
        return WebhookAck(accepted=False, reason="Auto sync is paused for this source")
    _schedule(source_id, after)
    return WebhookAck(accepted=True, reason=f"Sync scheduled for {after[:7]}")
