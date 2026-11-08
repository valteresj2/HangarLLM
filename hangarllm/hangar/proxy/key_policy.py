"""Rules every virtual key must meet, so a leaked key has a bounded lifetime, cost and reach.

A key follows the rules of its project's ``metadata.environment``. Keys with no project, or in a project
that is not marked ``production``, follow the stricter experiment rules. Production keys may skip the expiry,
in exchange for an IP restriction or automatic rotation.

Tune it under ``general_settings.key_policy``, or set ``enabled: false`` to turn it off.
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, Protocol

from fastapi import HTTPException, status

import hangarllm
from hangarllm.hangar.proxy.key_network import InvalidAllowedIps, allowed_networks
from hangarllm.hangarllm_core_utils.duration_parser import duration_in_seconds

DISABLE_ENV_VAR: Final = "HANGARLLM_DISABLE_KEY_POLICY"
ENVIRONMENT_FIELD: Final = "environment"
EXPERIMENT: Final = "experiment"
PRODUCTION: Final = "production"
_NEVER_EXPIRES: Final = frozenset({"", "-1"})
_NO_MODELS_NEEDED: Final = frozenset({"management", "read_only"})
_GOVERNED_FIELDS: Final = frozenset(
    {"duration", "max_budget", "budget_id", "models", "metadata", "auto_rotate", "rotation_interval", "key_alias", "project_id"}
)


@dataclass(frozen=True, slots=True)
class KeyPolicy:
    enabled: bool = True
    require_expiry: bool = True
    require_budget: bool = True
    require_models: bool = True
    max_duration: str | None = "90d"
    rotation_interval: str = "30d"


@dataclass(frozen=True, slots=True)
class KeyState:
    duration: str | None
    max_budget: float | None
    budget_id: str | None
    models: Sequence[str] | None
    key_type: object
    key_alias: str | None
    auto_rotate: bool | None
    rotation_interval: str | None
    metadata: object


class _KeyRequest(Protocol):
    duration: str | None
    max_budget: float | None
    budget_id: str | None
    models: Sequence[str] | None
    key_type: object
    key_alias: str | None
    auto_rotate: bool | None
    rotation_interval: str | None
    metadata: object


class _Team(Protocol):
    max_budget: float | None


def key_policy_from(general_settings: Mapping[str, object], environ: Mapping[str, str] = os.environ) -> KeyPolicy:
    configured: Final = general_settings.get("key_policy")
    values: Final = configured if isinstance(configured, Mapping) else {}
    known: Final = {name: values[name] for name in KeyPolicy.__dataclass_fields__ if name in values}
    policy: Final = KeyPolicy(**known)
    if environ.get(DISABLE_ENV_VAR, "").strip().lower() == "true":
        return KeyPolicy(enabled=False)
    return policy


def _key_type_name(key_type: object) -> str:
    return str(getattr(key_type, "value", key_type) or "")


def _rotation_can_deliver() -> bool:
    settings: Final = hangarllm._key_management_settings
    return settings is not None and bool(settings.store_virtual_keys)


def _seconds(duration: str) -> int | None:
    try:
        return duration_in_seconds(duration)
    except ValueError:
        return None


def _has_valid_networks(metadata: object) -> tuple[bool, bool]:
    """Whether the key is restricted to some network, and whether its restriction is well formed."""
    try:
        return bool(allowed_networks(metadata)), True
    except InvalidAllowedIps:
        return False, False


def key_policy_violations(
    data: _KeyRequest,
    team: _Team | None,
    policy: KeyPolicy,
    environment: str = EXPERIMENT,
    rotation_can_deliver: bool = False,
) -> tuple[str, ...]:
    if not policy.enabled:
        return ()
    duration: Final = None if data.duration is None or data.duration in _NEVER_EXPIRES else data.duration
    seconds: Final = _seconds(duration) if duration is not None else None
    too_long: Final = (
        seconds is not None and policy.max_duration is not None and seconds > duration_in_seconds(policy.max_duration)
    )
    production: Final = environment == PRODUCTION
    has_budget: Final = (
        data.max_budget is not None or data.budget_id is not None or (team is not None and team.max_budget is not None)
    )
    restricted, well_formed = _has_valid_networks(data.metadata)
    rotates: Final = rotation_can_deliver and bool(data.auto_rotate) and bool(data.rotation_interval)
    checks: Final = (
        (duration is not None and seconds is None, "duration is not valid, use a value like 30d"),
        (not production and policy.require_expiry and duration is None, "duration is required, for example 30d"),
        (not production and too_long, f"duration cannot be longer than {policy.max_duration}"),
        (policy.require_budget and not has_budget, "max_budget or budget_id is required, or a team with a budget"),
        (
            policy.require_models and not data.models and _key_type_name(data.key_type) not in _NO_MODELS_NEEDED,
            "models is required, list the models this key may call",
        ),
        (production and not data.key_alias, "key_alias is required for production keys"),
        (
            production and (duration is None or too_long) and not (restricted or rotates),
            "a long-lived production key needs metadata.allowed_ips, "
            "or auto_rotate with a rotation_interval and store_virtual_keys enabled",
        ),
        (
            not well_formed,
            "metadata.allowed_ips must list IP addresses or networks no wider than /8 for IPv4 or /32 for IPv6",
        ),
    )
    return tuple(message for failed, message in checks if failed)


def _reject(problems: Sequence[str]) -> None:
    if problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Key policy: " + "; ".join(problems) + "."},
        )


def enforce_key_policy(
    data: _KeyRequest, team: _Team | None, general_settings: Mapping[str, object], environment: str = EXPERIMENT
) -> None:
    policy: Final = key_policy_from(general_settings)
    if not policy.enabled:
        return
    deliverable: Final = _rotation_can_deliver()
    if data.auto_rotate is None and data.key_alias and deliverable:
        # A rotated value has to reach its owner, and a secret manager is the only delivery that does not need a person.
        data.auto_rotate = True
        data.rotation_interval = data.rotation_interval or policy.rotation_interval
    _reject(key_policy_violations(data, team, policy, environment, deliverable))


def validate_project_environment(metadata: object) -> None:
    value: Final = metadata.get(ENVIRONMENT_FIELD) if isinstance(metadata, Mapping) else None
    if value not in (None, EXPERIMENT, PRODUCTION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"metadata.environment must be '{EXPERIMENT}' or '{PRODUCTION}'."},
        )


async def _project_row(project_id: str | None):
    from hangarllm.proxy.proxy_server import prisma_client

    if project_id is None or prisma_client is None:
        return None
    return await prisma_client.writer_db.hangarllm_projecttable.find_unique(where={"project_id": project_id})


def _environment_of(project: object) -> str:
    metadata: Final = getattr(project, "metadata", None)
    return PRODUCTION if isinstance(metadata, Mapping) and metadata.get(ENVIRONMENT_FIELD) == PRODUCTION else EXPERIMENT


async def _require_production_key_manager(user: object, project: object) -> None:
    from hangarllm.hangar.proxy.projects import _is_proxy_admin, _team
    from hangarllm.proxy.management.teams.authz import is_team_admin

    if _is_proxy_admin(user):
        return
    team_id: Final = getattr(project, "team_id", None)
    team: Final = await _team(team_id) if team_id else None
    if team is None or not is_team_admin(user, team):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Only proxy admins or admins of the project's team can manage production keys."},
        )


async def enforce_new_key_policy(data, team: _Team | None, general_settings: Mapping[str, object], user: object) -> None:
    if not key_policy_from(general_settings).enabled:
        return
    project: Final = await _project_row(data.project_id)
    environment: Final = _environment_of(project)
    enforce_key_policy(data, team, general_settings, environment)
    if environment == PRODUCTION:
        await _require_production_key_manager(user, project)


def _remaining_duration(expires: datetime | str | None) -> str | None:
    if expires is None:
        return None
    moment: Final = datetime.fromisoformat(expires.replace("Z", "+00:00")) if isinstance(expires, str) else expires
    aware: Final = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return f"{max(1, int((aware - datetime.now(timezone.utc)).total_seconds()))}s"


def _stored_state(key: object) -> KeyState:
    return KeyState(
        duration=_remaining_duration(getattr(key, "expires", None)),
        max_budget=getattr(key, "max_budget", None),
        budget_id=getattr(key, "budget_id", None),
        models=getattr(key, "models", None),
        key_type=getattr(key, "key_type", None),
        key_alias=getattr(key, "key_alias", None),
        auto_rotate=getattr(key, "auto_rotate", None),
        rotation_interval=getattr(key, "rotation_interval", None),
        metadata=getattr(key, "metadata", None),
    )


def _state_after_update(key: object, data) -> KeyState:
    stored: Final = _stored_state(key)
    fields: Final = data.model_fields_set

    def updated(name: str):
        return getattr(data, name) if name in fields else getattr(stored, name)

    keeps_expiry: Final = "duration" not in fields or data.duration == ""
    return KeyState(
        duration=stored.duration if keeps_expiry else data.duration,
        max_budget=updated("max_budget"),
        budget_id=updated("budget_id"),
        models=updated("models"),
        key_type=stored.key_type,
        key_alias=updated("key_alias"),
        auto_rotate=updated("auto_rotate"),
        rotation_interval=updated("rotation_interval"),
        metadata=updated("metadata"),
    )


async def enforce_key_update_policy(
    data, key: object, team: _Team | None, general_settings: Mapping[str, object], user: object
) -> None:
    """Refuse an update that weakens a key. Gaps a key already had, from before the policy, do not block other edits."""
    policy: Final = key_policy_from(general_settings)
    if not policy.enabled or not data.model_fields_set & _GOVERNED_FIELDS:
        return
    current_id: Final = getattr(key, "project_id", None)
    target_id: Final = data.project_id if "project_id" in data.model_fields_set else current_id
    current_project: Final = await _project_row(current_id)
    target_project: Final = current_project if target_id == current_id else await _project_row(target_id)
    environment_before: Final = _environment_of(current_project)
    environment_after: Final = _environment_of(target_project)
    deliverable: Final = _rotation_can_deliver()
    before: Final = key_policy_violations(_stored_state(key), team, policy, environment_before, deliverable)
    after: Final = key_policy_violations(_state_after_update(key, data), team, policy, environment_after, deliverable)
    _reject(tuple(problem for problem in after if problem not in before))
    for project in (current_project,) if target_id == current_id else (current_project, target_project):
        if _environment_of(project) == PRODUCTION:
            await _require_production_key_manager(user, project)
