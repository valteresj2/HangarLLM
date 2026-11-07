"""
Projects API - a layer between teams and keys.

A project belongs to one team and groups keys that share a model allow-list,
per-model rate limits, a budget and object permissions (MCP servers, vector
stores, agents, ...).

``POST   /project/new``     create (proxy admin, or team admin when the team-admin
                            ``projects`` permission is enabled)
``POST   /project/update``  update (same rule)
``DELETE /project/delete``  delete one or more projects (proxy admin or team admin)
``GET    /project/info``    one project (admins, or members of its team)
``GET    /project/list``    projects visible to the caller
"""

import json
from collections.abc import Mapping
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Query, status

from litellm._logging import verbose_proxy_logger
from litellm.hangar.proxy._auth import require_db
from litellm.proxy._types import (
    DeleteProjectRequest,
    LitellmUserRoles,
    NewProjectRequest,
    UpdateProjectRequest,
    UserAPIKeyAuth,
)
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()
_AUTH: Final = Depends(user_api_key_auth)

_BUDGET_FIELDS: Final = (
    "max_budget",
    "soft_budget",
    "max_parallel_requests",
    "tpm_limit",
    "rpm_limit",
    "tpd_limit",
    "model_max_budget",
    "budget_duration",
    "allowed_models",
    "temp_budget_increase",
    "temp_budget_expiry",
)
_JSON_FIELDS: Final = frozenset({"metadata", "model_rpm_limit", "model_tpm_limit", "model_max_budget", "model_spend"})


def _role(user: UserAPIKeyAuth) -> str | None:
    role: Final = user.user_role
    return role.value if isinstance(role, LitellmUserRoles) else role


def _is_proxy_admin(user: UserAPIKeyAuth) -> bool:
    return _role(user) == LitellmUserRoles.PROXY_ADMIN.value


def _is_admin_viewer(user: UserAPIKeyAuth) -> bool:
    return _role(user) in (LitellmUserRoles.PROXY_ADMIN.value, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY.value)


def _changed_by(user: UserAPIKeyAuth) -> str:
    from litellm.proxy.proxy_server import litellm_proxy_admin_name

    return user.user_id or litellm_proxy_admin_name or "hangarllm"


def _db_value(field: str, value: object) -> object:
    return json.dumps(value) if field in _JSON_FIELDS and isinstance(value, (dict, list)) else value


async def _team(team_id: str):
    from litellm.proxy.auth.auth_checks import get_team_object
    from litellm.proxy.proxy_server import prisma_client, proxy_logging_obj, user_api_key_cache

    try:
        return await get_team_object(
            team_id=team_id,
            prisma_client=prisma_client,
            user_api_key_cache=user_api_key_cache,
            proxy_logging_obj=proxy_logging_obj,
            check_db_only=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail={"error": f"Team {team_id} not found"}) from e


async def _require_team_manager(user: UserAPIKeyAuth, team_id: str) -> None:
    if _is_proxy_admin(user):
        return
    from litellm.proxy.management.teams.authz import is_team_admin
    from litellm.proxy.management_endpoints.team_admin_field_permissions import team_admin_may_manage_projects
    from litellm.proxy.proxy_server import general_settings

    team: Final = await _team(team_id)
    if team is not None and is_team_admin(user, team) and team_admin_may_manage_projects(general_settings):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "Only proxy admins, or team admins with the 'projects' permission, can manage projects."},
    )


async def _visible_team_ids(user: UserAPIKeyAuth) -> list[str] | None:
    """None means 'all teams' (admins)."""
    if _is_admin_viewer(user):
        return None
    prisma_client: Final = require_db()
    if not user.user_id:
        return [user.team_id] if user.team_id else []
    from litellm.repositories.user_repository import UserRepository

    row: Final = await UserRepository(prisma_client).table.find_unique(where={"user_id": user.user_id})
    teams: Final = list(getattr(row, "teams", None) or [])
    if user.team_id and user.team_id not in teams:
        teams.append(user.team_id)
    return teams


async def _create_budget(data: NewProjectRequest | UpdateProjectRequest, changed_by: str) -> str | None:
    values: Final = {f: getattr(data, f, None) for f in _BUDGET_FIELDS if getattr(data, f, None) is not None}
    if not values:
        return None
    prisma_client: Final = require_db()
    from litellm.repositories.budget_repository import BudgetRepository

    payload: Final = {k: _db_value(k, v) for k, v in values.items()}
    payload.update({"created_by": changed_by, "updated_by": changed_by})
    budget: Final = await BudgetRepository(prisma_client).table.create(data=payload)
    return budget.budget_id


async def _update_budget(budget_id: str, data: UpdateProjectRequest, changed_by: str) -> None:
    values: Final = {f: getattr(data, f, None) for f in _BUDGET_FIELDS if getattr(data, f, None) is not None}
    if not values:
        return
    prisma_client: Final = require_db()
    from litellm.repositories.budget_repository import BudgetRepository

    payload: Final = {k: _db_value(k, v) for k, v in values.items()}
    payload["updated_by"] = changed_by
    await BudgetRepository(prisma_client).table.update(where={"budget_id": budget_id}, data=payload)


async def _create_object_permission(permission: object) -> str | None:
    if permission is None:
        return None
    prisma_client: Final = require_db()
    from litellm.repositories.object_permission_repository import ObjectPermissionRepository

    dumped: Final = permission.model_dump(exclude_none=True)  # type: ignore[attr-defined]
    if not dumped:
        return None
    payload: Final = {k: _db_value(k, v) if k == "mcp_tool_permissions" else v for k, v in dumped.items()}
    if "mcp_tool_permissions" in payload and isinstance(dumped.get("mcp_tool_permissions"), dict):
        payload["mcp_tool_permissions"] = json.dumps(dumped["mcp_tool_permissions"])
    row: Final = await ObjectPermissionRepository(prisma_client).table.create(data=payload)
    return row.object_permission_id


async def _evict(project_id: str) -> None:
    try:
        from litellm.proxy.auth.auth_checks import delete_cached_project_object
        from litellm.proxy.proxy_server import user_api_key_cache

        await delete_cached_project_object(project_id=project_id, user_api_key_cache=user_api_key_cache)
    except Exception as e:  # noqa: BLE001 - cache eviction is best effort
        verbose_proxy_logger.debug("HangarLLM: project cache eviction failed - %s", e)


def _serialise(row: object) -> dict:
    data: Final = row.model_dump() if hasattr(row, "model_dump") else dict(row)  # type: ignore[call-overload]
    for key in ("created_at", "updated_at"):
        value = data.get(key)
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    return data


async def _fetch(project_id: str):
    prisma_client: Final = require_db()
    from litellm.repositories.project_repository import ProjectRepository

    row: Final = await ProjectRepository(prisma_client).table.find_unique(
        where={"project_id": project_id}, include={"litellm_budget_table": True, "object_permission": True}
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": f"Project {project_id} not found"})
    return row


@router.post("/project/new", tags=["project management"])
async def new_project(
    data: NewProjectRequest,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> dict:
    """Create a project inside a team."""
    prisma_client: Final = require_db()
    await _require_team_manager(user_api_key_dict, data.team_id)
    changed_by: Final = _changed_by(user_api_key_dict)
    from litellm.repositories.project_repository import ProjectRepository

    if data.project_alias:
        existing = await ProjectRepository(prisma_client).table.find_first(
            where={"project_alias": data.project_alias, "team_id": data.team_id}
        )
        if existing is not None:
            raise HTTPException(
                status_code=400, detail={"error": f"Project alias '{data.project_alias}' already exists in this team"}
            )
    budget_id: Final = data.budget_id or await _create_budget(data, changed_by)
    object_permission_id: Final = await _create_object_permission(data.object_permission)
    payload: dict[str, object] = {  # mutable-ok: prisma payload
        "team_id": data.team_id,
        "models": data.models or [],
        "blocked": data.blocked,
        "created_by": changed_by,
        "updated_by": changed_by,
        "metadata": json.dumps(data.metadata or {}),
        "model_rpm_limit": json.dumps(data.model_rpm_limit or {}),
        "model_tpm_limit": json.dumps(data.model_tpm_limit or {}),
    }
    for field, value in (
        ("project_id", data.project_id),
        ("project_alias", data.project_alias),
        ("description", data.description),
        ("budget_id", budget_id),
        ("object_permission_id", object_permission_id),
    ):
        if value is not None:
            payload[field] = value
    row: Final = await ProjectRepository(prisma_client).table.create(
        data=payload, include={"litellm_budget_table": True, "object_permission": True}
    )
    return _serialise(row)


@router.post("/project/update", tags=["project management"])
async def update_project(
    data: UpdateProjectRequest,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> dict:
    """Update a project's settings, budget and permissions."""
    prisma_client: Final = require_db()
    current: Final = await _fetch(data.project_id)
    await _require_team_manager(user_api_key_dict, data.team_id or current.team_id)
    if data.team_id and data.team_id != current.team_id:
        await _require_team_manager(user_api_key_dict, current.team_id)
    changed_by: Final = _changed_by(user_api_key_dict)
    from litellm.repositories.project_repository import ProjectRepository

    payload: dict[str, object] = {"updated_by": changed_by}  # mutable-ok: prisma payload
    for field in ("project_alias", "description", "team_id", "models", "blocked", "budget_id"):
        value = getattr(data, field)
        if value is not None:
            payload[field] = value
    for field in ("metadata", "model_rpm_limit", "model_tpm_limit"):
        value = getattr(data, field)
        if value is not None:
            existing = getattr(current, field, None)
            merged = {**(existing if isinstance(existing, Mapping) else {}), **value} if field == "metadata" else value
            payload[field] = json.dumps(merged)
    if current.budget_id and not data.budget_id:
        await _update_budget(current.budget_id, data, changed_by)
    elif not current.budget_id and not data.budget_id:
        new_budget = await _create_budget(data, changed_by)
        if new_budget:
            payload["budget_id"] = new_budget
    if data.object_permission is not None:
        new_permission = await _create_object_permission(data.object_permission)
        if new_permission:
            payload["object_permission_id"] = new_permission
    row: Final = await ProjectRepository(prisma_client).table.update(
        where={"project_id": data.project_id},
        data=payload,
        include={"litellm_budget_table": True, "object_permission": True},
    )
    await _evict(data.project_id)
    return _serialise(row)


@router.delete("/project/delete", tags=["project management"])
async def delete_project(
    data: DeleteProjectRequest,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> list[dict]:
    """Delete projects. Keys attached to a project are detached, not deleted."""
    prisma_client: Final = require_db()
    from litellm.repositories.project_repository import ProjectRepository

    deleted: list[dict] = []  # mutable-ok: response accumulator
    for project_id in data.project_ids:
        row = await _fetch(project_id)
        await _require_team_manager(user_api_key_dict, row.team_id)
        try:
            await prisma_client.db.litellm_verificationtoken.update_many(
                where={"project_id": project_id}, data={"project_id": None}
            )
        except Exception as e:  # noqa: BLE001 - older schemas may not link keys
            verbose_proxy_logger.debug("HangarLLM: could not detach keys from project %s - %s", project_id, e)
        removed = await ProjectRepository(prisma_client).table.delete(where={"project_id": project_id})
        await _evict(project_id)
        deleted.append(_serialise(removed if removed is not None else row))
    return deleted


@router.get("/project/info", tags=["project management"])
async def project_info(
    project_id: str = Query(...),
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> dict:
    """Get one project."""
    row: Final = await _fetch(project_id)
    visible: Final = await _visible_team_ids(user_api_key_dict)
    if visible is not None and row.team_id not in visible:
        raise HTTPException(status_code=403, detail={"error": "You do not have access to this project"})
    return _serialise(row)


@router.get("/project/list", tags=["project management"])
async def list_projects(
    team_id: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> list[dict]:
    """List projects visible to the caller (all projects for admins)."""
    prisma_client: Final = require_db()
    from litellm.repositories.project_repository import ProjectRepository

    visible: Final = await _visible_team_ids(user_api_key_dict)
    where: dict[str, object] = {}  # mutable-ok: prisma filter
    if visible is not None:
        if team_id is not None and team_id not in visible:
            return []
        where["team_id"] = team_id if team_id is not None else {"in": visible}
    elif team_id is not None:
        where["team_id"] = team_id
    rows: Final = await ProjectRepository(prisma_client).table.find_many(
        where=where, include={"litellm_budget_table": True, "object_permission": True}, order={"created_at": "desc"}
    )
    return [_serialise(r) for r in rows]
