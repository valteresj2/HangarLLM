"""API contract for Skills Hub Git Sync (GitHub / GitHub Enterprise skill repositories)."""

import re
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

AuthType = Literal["none", "token", "github_app"]
SyncScope = Literal["all_keys", "access_group"]
PublishMode = Literal["auto", "approval"]
RemovePolicy = Literal["unpublish", "keep"]
SourceStatus = Literal["never_synced", "syncing", "healthy", "warnings", "failed", "pending_approval"]
SyncTrigger = Literal["create", "manual", "webhook", "poll", "approval", "rollback"]
SyncStatus = Literal[
    "applied", "applied_with_warnings", "no_changes", "pending_approval", "rejected", "superseded", "failed"
]
IssueSeverity = Literal["info", "warning", "error"]
SkillAction = Literal["created", "updated", "unchanged", "removed", "quarantined", "kept_previous"]

DEFAULT_GITHUB_API: Final = "https://api.github.com"
_OWNER_REPO: Final = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_BRANCH: Final = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _clean_path(value: str) -> str:
    parts: Final = tuple(p for p in value.replace("\\", "/").split("/") if p)
    if any(p in (".", "..") for p in parts):
        raise ValueError("skills_path must stay inside the repository")
    return "/".join(parts)


class GitConnection(_Frozen):
    auth_type: AuthType = "token"
    api_base_url: str = Field(default=DEFAULT_GITHUB_API, max_length=512)
    token: SecretStr | None = Field(default=None, description="Fine-grained token with read-only Contents access")
    app_id: str | None = Field(default=None, max_length=64)
    installation_id: str | None = Field(default=None, max_length=64)
    private_key: SecretStr | None = Field(default=None, description="GitHub App private key (PEM)")

    @field_validator("api_base_url")
    @classmethod
    def _https(cls, value: str) -> str:
        cleaned: Final = value.rstrip("/")
        if not cleaned.startswith("https://"):
            raise ValueError("api_base_url must use https")
        return cleaned


class GitRepository(_Frozen):
    full_name: str
    owner: str
    name: str
    default_branch: str
    private: bool
    description: str | None = None


class RepositoryList(_Frozen):
    repositories: tuple[GitRepository, ...]
    truncated: bool = False


class BranchQuery(_Frozen):
    connection: GitConnection
    owner: str
    repository: str


class BranchList(_Frozen):
    branches: tuple[str, ...]


class _SourceSettings(_Frozen):
    scope: SyncScope = "access_group"
    publish_mode: PublishMode = "auto"
    remove_policy: RemovePolicy = "unpublish"
    auto_sync: bool = True
    poll_interval_seconds: int = Field(default=300, ge=60, le=86400)


class GitSourceCreate(_SourceSettings):
    name: str = Field(min_length=1, max_length=100)
    connection: GitConnection
    owner: str
    repository: str
    branch: str = "main"
    skills_path: str = Field(default="", max_length=512)
    sync_now: bool = True

    @field_validator("owner", "repository")
    @classmethod
    def _repo_part(cls, value: str) -> str:
        if not _OWNER_REPO.fullmatch(value):
            raise ValueError("invalid GitHub owner or repository name")
        return value

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        if not _BRANCH.fullmatch(value) or ".." in value:
            raise ValueError("invalid branch name")
        return value

    @field_validator("skills_path")
    @classmethod
    def _path(cls, value: str) -> str:
        return _clean_path(value)


class GitSourceUpdate(_Frozen):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    connection: GitConnection | None = None
    branch: str | None = None
    skills_path: str | None = Field(default=None, max_length=512)
    scope: SyncScope | None = None
    publish_mode: PublishMode | None = None
    remove_policy: RemovePolicy | None = None
    auto_sync: bool | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=60, le=86400)

    @field_validator("branch")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        if value is not None and (not _BRANCH.fullmatch(value) or ".." in value):
            raise ValueError("invalid branch name")
        return value

    @field_validator("skills_path")
    @classmethod
    def _path(cls, value: str | None) -> str | None:
        return None if value is None else _clean_path(value)


class SyncIssue(_Frozen):
    severity: IssueSeverity
    code: str
    message: str
    file: str | None = None


class SkillOutcome(_Frozen):
    name: str | None
    path: str
    action: SkillAction
    version: str | None = None
    digest: str | None = None
    issues: tuple[SyncIssue, ...] = ()


class SyncSummary(_Frozen):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    quarantined: int = 0


class SyncReport(_Frozen):
    commit_sha: str | None
    applied: bool
    skills: tuple[SkillOutcome, ...] = ()
    issues: tuple[SyncIssue, ...] = ()
    summary: SyncSummary = SyncSummary()
    error: str | None = None


class GitSync(_Frozen):
    sync_id: str
    source_id: str
    commit_sha: str | None
    commit_url: str | None
    trigger: SyncTrigger
    status: SyncStatus
    report: SyncReport
    started_at: datetime
    finished_at: datetime | None
    triggered_by: str | None


class GitSyncList(_Frozen):
    syncs: tuple[GitSync, ...]


class GitSource(_Frozen):
    source_id: str
    name: str
    api_base_url: str
    owner: str
    repository: str
    repository_url: str
    branch: str
    skills_path: str
    auth_type: AuthType
    app_id: str | None
    installation_id: str | None
    has_credentials: bool
    scope: SyncScope
    access_group_id: str | None
    access_group_name: str | None
    publish_mode: PublishMode
    remove_policy: RemovePolicy
    auto_sync: bool
    poll_interval_seconds: int
    status: SourceStatus
    status_message: str | None
    last_seen_sha: str | None
    applied_sha: str | None
    last_checked_at: datetime | None
    last_synced_at: datetime | None
    managed_skills: tuple[str, ...]
    quarantined_skills: tuple[str, ...]
    webhook_url: str
    created_at: datetime
    created_by: str | None
    updated_at: datetime


class GitSourceList(_Frozen):
    sources: tuple[GitSource, ...]


class WebhookSetup(_Frozen):
    url: str
    secret: str
    content_type: Literal["application/json"] = "application/json"
    events: tuple[str, ...] = ("push",)


class GitSourceCreated(_Frozen):
    source: GitSource
    webhook: WebhookSetup
    sync: GitSync | None


class WebhookAck(_Frozen):
    accepted: bool
    reason: str
