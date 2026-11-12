import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter, field_validator

from hangarllm.models.credential_test import (
    CredentialTestKind,
    CredentialTestResult,
    CredentialTestStatus,
)
from hangarllm.repositories.table_repositories import HealthCheckRepository
from hangarllm.types.llms.base import HangarLLMBaseModel

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient

LATEST_CREDENTIAL_TESTS_SQL: Final = """
SELECT DISTINCT ON ("credential_name")
       "credential_name", "status", "error_message", "response_time_ms", "details", "checked_at"
FROM "HangarLLM_HealthCheckTable"
WHERE "credential_name" IS NOT NULL
ORDER BY "credential_name" ASC, "checked_at" DESC
"""


class _TestDetails(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    kind: CredentialTestKind | None = None
    http_status: int | None = None


class _LatestCredentialTestRow(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    credential_name: str
    status: CredentialTestStatus
    error_message: str | None = None
    response_time_ms: float | None = None
    details: _TestDetails | None = None
    checked_at: datetime

    @field_validator("details", mode="before")
    @classmethod
    def _decode_json_text(cls, value: object) -> object:
        return json.loads(value) if isinstance(value, str) else value

    @field_validator("checked_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    def as_result(self) -> CredentialTestResult:
        details: Final = self.details or _TestDetails()
        return CredentialTestResult(
            credential_name=self.credential_name,
            status=self.status,
            kind=details.kind,
            http_status=details.http_status,
            error=self.error_message,
            latency_ms=self.response_time_ms,
            checked_at=self.checked_at,
        )


_ROWS_ADAPTER: Final = TypeAdapter(tuple[_LatestCredentialTestRow, ...])


class CredentialTestRepository:
    def __init__(self, prisma_client: "PrismaClient") -> None:
        self._prisma_client = prisma_client

    async def save_result(self, result: CredentialTestResult, provider: str, checked_by: str | None) -> None:
        await HealthCheckRepository(self._prisma_client).table.create(
            data={
                "model_name": provider,
                "credential_name": result.credential_name,
                "status": result.status,
                "healthy_count": 1 if result.status == "healthy" else 0,
                "unhealthy_count": 1 if result.status == "failing" else 0,
                "error_message": result.error,
                "response_time_ms": result.latency_ms,
                "details": _TestDetails(kind=result.kind, http_status=result.http_status).model_dump_json(),
                "checked_by": checked_by,
                "checked_at": result.checked_at,
            }
        )

    async def latest_results(self) -> tuple[CredentialTestResult, ...]:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            LATEST_CREDENTIAL_TESTS_SQL
        )
        return tuple(row.as_result() for row in _ROWS_ADAPTER.validate_python(rows or ()))
