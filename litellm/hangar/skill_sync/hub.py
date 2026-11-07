"""Skills Hub adapter used by Git Sync: publish through the same versioned store as manual uploads."""

import asyncio
import hashlib
from typing import TYPE_CHECKING, Final

from litellm.hangar.skill_sync.apply import ExistingSkill
from litellm.models.plugin_upload import PluginPublication, PluginPublicationBase, PluginPublicationError, PluginReview
from litellm.proxy.anthropic_endpoints.claude_code_endpoints.skill_upload_archive import build_uploaded_skill_archive
from litellm.proxy.discovery_endpoints.agent_skills_archive import SkillArchive, build_agent_skill_archive
from litellm.repositories.plugin_upload_repository import PluginUploadRepository
from litellm.repositories.table_repositories import AccessGroupRepository, ClaudeCodePluginRepository

if TYPE_CHECKING:
    from litellm.proxy.utils import PrismaClient as Prisma


class SkillPublishError(Exception):
    pass


def archive_url(base_url: str, name: str, digest: str) -> str:
    from litellm.proxy.utils import get_custom_url

    return get_custom_url(request_base_url=base_url, route=f"claude-code/plugins/{name}/archive/{digest}.zip")


async def build_publication(
    archive: SkillArchive, *, base_url: str, origin: str, created_by: str, reviewer: str
) -> PluginPublication:
    name: Final = archive.declared_name
    if name is None:
        raise SkillPublishError("SKILL.md must declare a skill name")
    plugin: Final = await asyncio.to_thread(build_uploaded_skill_archive, archive.content, name)
    if plugin is None:
        raise SkillPublishError("Skill exceeds the supported archive limits")
    portable: Final = await asyncio.to_thread(build_agent_skill_archive, plugin, plugin_name=name)
    if portable is None or portable.digest != archive.digest:
        raise SkillPublishError("Skill exceeds the supported archive limits after compatibility packaging")
    digest: Final = hashlib.sha256(plugin).hexdigest()
    return PluginPublication(
        name=name,
        version=None,
        description=archive.declared_description,
        manifest={
            "name": name,
            "description": archive.declared_description,
            "version": None,
            "source": {"source": "archive", "url": archive_url(base_url, name, digest), "sha256": digest},
            "agent_skill": {
                "name": name,
                "description": archive.declared_description,
                "digest": archive.digest,
                "origin": origin,
            },
        },
        content=plugin,
        created_by=created_by,
        review=PluginReview(approved_by=reviewer, security_scan_passed=True),
    )


class PrismaHub:
    def __init__(self, prisma: "Prisma", *, base_url: str, actor: str, reviewer: str) -> None:
        self._prisma: Final = prisma
        self._store: Final = PluginUploadRepository(prisma)
        self._base_url: Final = base_url
        self._actor: Final = actor
        self._reviewer: Final = reviewer
        self._bases: dict[str, PluginPublicationBase] = {}  # mutable-ok: optimistic-lock bases per sync

    async def existing(self, name: str) -> ExistingSkill | None:
        snapshot: Final = await self._store.get_plugin(name)
        if snapshot is None:
            return None
        if snapshot.updated_at is not None:
            self._bases[name] = PluginPublicationBase(snapshot.id, snapshot.updated_at)
        agent: Final = snapshot.manifest.get("agent_skill")
        digest: Final = agent.get("digest") if isinstance(agent, dict) else None
        return ExistingSkill(
            name=name,
            version=snapshot.version,
            digest=digest if isinstance(digest, str) else None,
            enabled=snapshot.enabled,
        )

    async def publish(self, archive: SkillArchive, origin: str, existing: ExistingSkill | None) -> str:
        publication: Final = await build_publication(
            archive, base_url=self._base_url, origin=origin, created_by=self._actor, reviewer=self._reviewer
        )
        expected: Final = self._bases.get(publication.name) if existing is not None else None
        result: Final = await self._store.publish(publication, expected)
        if isinstance(result, PluginPublicationError) and result.kind == "conflict" and existing is not None:
            legacy: Final = await self._store.publish(
                PluginPublication(**{**_fields(publication), "version": "1.0.0"}), expected
            )
            if isinstance(legacy, PluginPublicationError):
                raise SkillPublishError(legacy.message)
            return legacy.version or "1.0.0"
        if isinstance(result, PluginPublicationError):
            raise SkillPublishError(result.message)
        return result.version or "1.0.0"

    async def set_enabled(self, name: str, enabled: bool) -> None:
        from datetime import datetime, timezone

        table: Final = ClaudeCodePluginRepository(self._prisma, use_writer=True).table
        current: Final = await table.find_unique(where={"name": name})
        if current is None or current.enabled == enabled:
            return
        await table.update(where={"name": name}, data={"enabled": enabled, "updated_at": datetime.now(timezone.utc)})

    async def sync_access_group(self, group_name: str, skill_names: tuple[str, ...]) -> str:
        from litellm.proxy.management_helpers.access_group_team_sync import invalidate_access_group_cache

        table: Final = AccessGroupRepository(self._prisma, use_writer=True).table
        current: Final = await table.find_unique(where={"access_group_name": group_name})
        if current is None:
            created: Final = await table.create(
                data={
                    "access_group_name": group_name,
                    "description": "Skills synced from GitHub by HangarLLM. Attach this group to teams or keys.",
                    "access_skill_names": list(skill_names),
                    "created_by": self._actor,
                    "updated_by": self._actor,
                }
            )
            return created.access_group_id
        if sorted(current.access_skill_names or []) != sorted(skill_names):
            await table.update(
                where={"access_group_id": current.access_group_id},
                data={"access_skill_names": list(skill_names), "updated_by": self._actor},
            )
            await invalidate_access_group_cache(current.access_group_id)
        return current.access_group_id


def _fields(publication: PluginPublication) -> dict[str, object]:
    return {
        "name": publication.name,
        "version": publication.version,
        "description": publication.description,
        "manifest": publication.manifest,
        "created_by": publication.created_by,
        "content": publication.content,
        "review": publication.review,
    }
