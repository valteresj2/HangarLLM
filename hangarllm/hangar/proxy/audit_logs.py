"""
Audit log API.

``GET /audit``       paginated, filterable list of management changes
``GET /audit/{id}``  one entry

Audit rows are written by core when ``hangarllm_settings.store_audit_logs: true``.
"""

import json
import math
from datetime import datetime
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.proxy._auth import require_db, require_proxy_admin_or_viewer
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()
_AUTH: Final = Depends(user_api_key_auth)

_SORTABLE: Final = frozenset({"updated_at", "changed_by", "action", "table_name", "object_id"})


class AuditLogResponse(BaseModel):
    id: str
    updated_at: str
    changed_by: str
    changed_by_api_key: str
    action: str
    table_name: str
    object_id: str
    before_value: dict | None = None
    updated_values: dict | None = None


class PaginatedAuditLogResponse(BaseModel):
    audit_logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


def _json_obj(value: object) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {"value": value}
    return value if isinstance(value, dict) else {"value": value}


def _to_response(row: object) -> AuditLogResponse:
    updated_at: Final = getattr(row, "updated_at", None)
    return AuditLogResponse(
        id=str(getattr(row, "id", "")),
        updated_at=updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at or ""),
        changed_by=str(getattr(row, "changed_by", "") or ""),
        changed_by_api_key=str(getattr(row, "changed_by_api_key", "") or ""),
        action=str(getattr(row, "action", "") or ""),
        table_name=str(getattr(row, "table_name", "") or ""),
        object_id=str(getattr(row, "object_id", "") or ""),
        before_value=_json_obj(getattr(row, "before_value", None)),
        updated_values=_json_obj(getattr(row, "updated_values", None)),
    )


def _parse_date(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": f"{field} must be an ISO-8601 date"}) from e


def build_audit_where(
    *,
    changed_by: str | None = None,
    changed_by_api_key: str | None = None,
    action: str | None = None,
    table_name: str | None = None,
    object_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    object_team_id: str | None = None,
    object_key_hash: str | None = None,
    search: str | None = None,
) -> dict:
    where: dict[str, object] = {}  # mutable-ok: prisma filter built per request
    for field, value in (
        ("changed_by", changed_by),
        ("changed_by_api_key", changed_by_api_key),
        ("action", action),
        ("table_name", table_name),
        ("object_id", object_id),
    ):
        if value:
            where[field] = value
    start: Final = _parse_date(start_date, "start_date")
    end: Final = _parse_date(end_date, "end_date")
    if start or end:
        where["updated_at"] = {k: v for k, v in (("gte", start), ("lte", end)) if v is not None}
    and_clauses: list[dict] = []  # mutable-ok
    for json_field, value in (("team_id", object_team_id), ("token", object_key_hash)):
        if value:
            and_clauses.append(
                {
                    "OR": [
                        {"updated_values": {"path": [json_field], "equals": value}},
                        {"before_value": {"path": [json_field], "equals": value}},
                    ]
                }
            )
    if search:
        and_clauses.append(
            {
                "OR": [
                    {"object_id": {"contains": search, "mode": "insensitive"}},
                    {"changed_by": {"contains": search, "mode": "insensitive"}},
                    {"table_name": {"contains": search, "mode": "insensitive"}},
                    {"action": {"contains": search, "mode": "insensitive"}},
                ]
            }
        )
    if and_clauses:
        where["AND"] = and_clauses
    return where


@router.get("/audit", tags=["Audit Logging"], response_model=PaginatedAuditLogResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    changed_by: str | None = None,
    changed_by_api_key: str | None = None,
    action: str | None = None,
    table_name: str | None = None,
    object_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    object_team_id: str | None = None,
    object_key_hash: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> PaginatedAuditLogResponse:
    """List audit log entries with filtering, search, sorting and pagination."""
    require_proxy_admin_or_viewer(user_api_key_dict)
    prisma_client: Final = require_db()
    from hangarllm.repositories.table_repositories import AuditLogRepository

    where: Final = build_audit_where(
        changed_by=changed_by,
        changed_by_api_key=changed_by_api_key,
        action=action,
        table_name=table_name,
        object_id=object_id,
        start_date=start_date,
        end_date=end_date,
        object_team_id=object_team_id,
        object_key_hash=object_key_hash,
        search=search,
    )
    order_field: Final = sort_by if sort_by in _SORTABLE else "updated_at"
    order_dir: Final = "asc" if str(sort_order).lower() == "asc" else "desc"
    table: Final = AuditLogRepository(prisma_client).table
    try:
        rows = await table.find_many(
            where=where, skip=(page - 1) * page_size, take=page_size, order={order_field: order_dir}
        )
        total = await table.count(where=where)
    except Exception as e:
        verbose_proxy_logger.exception("HangarLLM: audit log query failed")
        raise HTTPException(status_code=500, detail={"error": f"Audit log query failed: {e}"}) from e
    return PaginatedAuditLogResponse(
        audit_logs=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)) if total else 0,
    )


@router.get("/audit/{id}", tags=["Audit Logging"], response_model=AuditLogResponse)
async def get_audit_log_by_id(
    id: str,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> AuditLogResponse:
    """Get one audit log entry."""
    require_proxy_admin_or_viewer(user_api_key_dict)
    prisma_client: Final = require_db()
    from hangarllm.repositories.table_repositories import AuditLogRepository

    row: Final = await AuditLogRepository(prisma_client).table.find_unique(where={"id": id})
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": f"Audit log {id} not found"})
    return _to_response(row)
