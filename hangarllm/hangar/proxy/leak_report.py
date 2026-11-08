"""Revoke virtual keys that a scanner found in public.

Scanners post a signed list in the GitHub secret scanning partner shape. The endpoint has no API key
auth because the reporter has none. Set ``HANGARLLM_LEAK_REPORT_SECRET`` to enable it.
"""

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Final, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from hangarllm._logging import verbose_proxy_logger
from hangarllm.constants import VIRTUAL_KEY_PREFIXES
from hangarllm.proxy.utils import hash_token

SECRET_ENV_VAR: Final = "HANGARLLM_LEAK_REPORT_SECRET"
_MAX_REPORTED_KEYS: Final = 100
router: Final = APIRouter(tags=["key management"])


class LeakedKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    token: str
    url: str | None = None
    source: str | None = None


class LeakVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_type: Literal["hangarllm_virtual_key"] = "hangarllm_virtual_key"
    label: Literal["true_positive", "false_positive"]


_REPORT: Final = TypeAdapter(tuple[LeakedKey, ...])


def valid_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    return hmac.compare_digest("sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), signature)


async def _record_revocation(hashed: str, report: LeakedKey) -> None:
    from hangarllm.proxy._types import HangarLLM_AuditLogs, HangarllmTableNames
    from hangarllm.proxy.auth.auth_checks import delete_cache_key_objects
    from hangarllm.proxy.management_helpers.audit_logs import create_audit_log_for_update
    from hangarllm.proxy.proxy_server import proxy_logging_obj, user_api_key_cache
    from hangarllm.types.integrations.slack_alerting import AlertType

    await delete_cache_key_objects(
        hashed_tokens=(hashed,), user_api_key_cache=user_api_key_cache, proxy_logging_obj=proxy_logging_obj
    )
    await create_audit_log_for_update(
        HangarLLM_AuditLogs(
            id=str(uuid.uuid4()),
            updated_at=datetime.now(timezone.utc),
            changed_by="leak-report",
            changed_by_api_key="",
            action="blocked",
            table_name=HangarllmTableNames.KEY_TABLE_NAME,
            object_id=hashed,
            updated_values=json.dumps({"blocked": True, "reason": "leak_report", "url": report.url}),
        )
    )
    await proxy_logging_obj.alerting_handler(
        message=f"A virtual key was found in public and has been blocked. Source: {report.url or report.source or '?'}",
        level="High",
        alert_type=AlertType.key_leak_alerts,
    )


async def _revoke(report: LeakedKey) -> LeakVerdict:
    from hangarllm.proxy.proxy_server import prisma_client

    if not report.token.startswith(VIRTUAL_KEY_PREFIXES) or prisma_client is None:
        return LeakVerdict(label="false_positive")
    hashed: Final = hash_token(token=report.token)
    blocked: Final = await prisma_client.db.hangarllm_verificationtoken.update_many(
        where={"token": hashed}, data={"blocked": True}
    )
    if blocked == 0:
        return LeakVerdict(label="false_positive")
    verbose_proxy_logger.warning("Blocked a virtual key reported as leaked by %s", report.source or "a scanner")
    await _record_revocation(hashed, report)
    return LeakVerdict(label="true_positive")


@router.post("/key/leak-report", response_model=tuple[LeakVerdict, ...])
async def report_leaked_keys(request: Request) -> tuple[LeakVerdict, ...]:
    secret: Final = os.getenv(SECRET_ENV_VAR)
    if not secret:
        raise HTTPException(404, {"error": "Leak reporting is not enabled"})
    body: Final = await request.body()
    if not valid_signature(secret, body, request.headers.get("x-hangar-signature")):
        raise HTTPException(401, {"error": "Invalid signature"})
    try:
        reports: Final = _REPORT.validate_json(body)
    except ValidationError:
        raise HTTPException(400, {"error": "Expected a JSON list of objects with a token field"})
    if len(reports) > _MAX_REPORTED_KEYS:
        raise HTTPException(413, {"error": f"At most {_MAX_REPORTED_KEYS} keys per report"})
    return tuple([await _revoke(report) for report in reports])
