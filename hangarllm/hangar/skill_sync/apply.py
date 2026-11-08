"""Turn a repository discovery into Skills Hub changes (or a dry-run plan for approval mode)."""

from dataclasses import dataclass
from typing import Final, Protocol

from hangarllm.hangar.skill_sync.discovery import DiscoveredSkill, Discovery
from hangarllm.hangar.skill_sync.types import (
    RemovePolicy,
    SkillOutcome,
    SyncIssue,
    SyncReport,
    SyncScope,
    SyncSummary,
)
from hangarllm.proxy.discovery_endpoints.agent_skills_archive import SkillArchive


@dataclass(frozen=True, slots=True)
class ExistingSkill:
    name: str
    version: str | None
    digest: str | None
    enabled: bool


class HubPort(Protocol):
    async def existing(self, name: str) -> ExistingSkill | None: ...

    async def publish(self, archive: SkillArchive, origin: str, existing: ExistingSkill | None) -> str: ...

    async def set_enabled(self, name: str, enabled: bool) -> None: ...

    async def sync_access_group(self, group_name: str, skill_names: tuple[str, ...]) -> str: ...


@dataclass(frozen=True, slots=True)
class SyncTarget:
    owner: str
    repository: str
    commit_sha: str
    origin_base: str
    scope: SyncScope
    remove_policy: RemovePolicy
    managed_skills: frozenset[str]

    @property
    def access_group_name(self) -> str:
        return access_group_name(self.owner, self.repository)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    report: SyncReport
    managed_skills: tuple[str, ...]
    quarantined_skills: tuple[str, ...]
    access_group_id: str | None
    changed: bool


def access_group_name(owner: str, repository: str) -> str:
    return f"git:{owner}/{repository}"


def _conflict(name: str) -> SyncIssue:
    return SyncIssue(
        severity="error",
        code="name_conflict",
        message=f"A skill named '{name}' already exists in the hub and is not managed by this repository. "
        "Rename the skill in the repository or delete the existing hub skill.",
    )


def _label(skill: DiscoveredSkill) -> str:
    return skill.name or skill.path.rpartition("/")[2] or skill.path or "(repository root)"


async def _outcome(
    skill: DiscoveredSkill, target: SyncTarget, hub: HubPort, apply: bool
) -> tuple[SkillOutcome, str | None]:
    """Outcome for one discovered skill plus the name that stays live after the sync (if any)."""
    label: Final = _label(skill)
    existing: Final = await hub.existing(label)
    owned: Final = label in target.managed_skills
    if skill.blocked or skill.archive is None:
        keeps_previous: Final = owned and existing is not None
        return (
            SkillOutcome(
                name=label,
                path=skill.path,
                action="kept_previous" if keeps_previous else "quarantined",
                version=existing.version if keeps_previous and existing is not None else None,
                issues=skill.issues,
            ),
            label if keeps_previous else None,
        )
    archive: Final = skill.archive
    if existing is not None and not owned:
        return (
            SkillOutcome(name=label, path=skill.path, action="quarantined", issues=(*skill.issues, _conflict(label))),
            None,
        )
    if existing is not None and existing.digest == archive.digest:
        return (
            SkillOutcome(
                name=label,
                path=skill.path,
                action="unchanged",
                version=existing.version,
                digest=archive.digest,
                issues=skill.issues,
            ),
            label,
        )
    origin: Final = f"{target.origin_base}/tree/{target.commit_sha}/{skill.path}".rstrip("/")
    version: Final = await hub.publish(archive, origin, existing) if apply else None
    return (
        SkillOutcome(
            name=label,
            path=skill.path,
            action="updated" if existing is not None else "created",
            version=version,
            digest=archive.digest,
            issues=skill.issues,
        ),
        label,
    )


async def apply_discovery(discovery: Discovery, target: SyncTarget, hub: HubPort, *, apply: bool) -> ApplyResult:
    pairs: Final = tuple([await _outcome(skill, target, hub, apply) for skill in discovery.skills])
    outcomes: Final = tuple(o for o, _ in pairs)
    live: Final = tuple(sorted({name for _, name in pairs if name is not None}))
    seen: Final = frozenset(o.name for o in outcomes if o.name is not None)
    gone: Final = tuple(sorted([name for name in target.managed_skills - seen if await hub.existing(name) is not None]))
    unpublish: Final = target.remove_policy == "unpublish"
    removed: Final = tuple(
        SkillOutcome(
            name=name,
            path="",
            action="removed" if unpublish else "unchanged",
            issues=(
                SyncIssue(
                    severity="info",
                    code="removed_from_repository",
                    message="Deleted from the repository; unpublished from the hub"
                    if unpublish
                    else "Deleted from the repository; kept in the hub (remove policy: keep)",
                ),
            ),
        )
        for name in gone
    )
    kept_live: Final = live if unpublish else tuple(sorted({*live, *gone}))
    group_id: Final = await _apply_scope(target, hub, kept_live, gone if unpublish else ()) if apply else None
    created: Final = frozenset(o.name for o in outcomes if o.action == "created" and o.name is not None)
    all_outcomes: Final = (*outcomes, *removed)
    summary: Final = SyncSummary(
        created=sum(1 for o in all_outcomes if o.action == "created"),
        updated=sum(1 for o in all_outcomes if o.action == "updated"),
        unchanged=sum(1 for o in all_outcomes if o.action == "unchanged"),
        removed=sum(1 for o in all_outcomes if o.action == "removed"),
        quarantined=sum(1 for o in all_outcomes if o.action in ("quarantined", "kept_previous")),
    )
    return ApplyResult(
        report=SyncReport(
            commit_sha=target.commit_sha, applied=apply, skills=all_outcomes, issues=discovery.issues, summary=summary
        ),
        managed_skills=tuple(sorted(target.managed_skills | created)),
        quarantined_skills=tuple(
            sorted(o.name for o in outcomes if o.action in ("quarantined", "kept_previous") and o.name is not None)
        ),
        access_group_id=group_id,
        changed=bool(summary.created or summary.updated or summary.removed),
    )


async def _apply_scope(
    target: SyncTarget, hub: HubPort, live: tuple[str, ...], unpublished: tuple[str, ...]
) -> str | None:
    for name in unpublished:
        await hub.set_enabled(name, False)
    if target.scope == "all_keys":
        for name in live:
            await hub.set_enabled(name, True)
        return await hub.sync_access_group(target.access_group_name, live)
    for name in live:
        await hub.set_enabled(name, False)
    return await hub.sync_access_group(target.access_group_name, live)
