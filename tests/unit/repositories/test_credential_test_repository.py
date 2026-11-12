import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest

from hangarllm.models.credential_test import CredentialTestResult
from hangarllm.repositories.credential_test_repository import (
    LATEST_CREDENTIAL_TESTS_SQL,
    CredentialTestRepository,
)

T0: Final = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


def _prisma(rows: Sequence[Mapping[str, object]]) -> MagicMock:
    prisma: Final = MagicMock()
    prisma.db.query_raw = AsyncMock(return_value=list(rows))
    prisma.db.hangarllm_healthchecktable.create = AsyncMock(return_value=None)
    return prisma


@pytest.mark.asyncio
async def test_a_saved_result_round_trips_through_the_latest_query():
    prisma: Final = _prisma([])
    repository: Final = CredentialTestRepository(prisma)
    result: Final = CredentialTestResult(
        credential_name="openai-prod",
        status="failing",
        kind="model_list",
        http_status=401,
        error="HTTP 401",
        latency_ms=41.5,
        checked_at=T0,
    )

    await repository.save_result(result, provider="openai", checked_by="admin-user")
    written: Final = prisma.db.hangarllm_healthchecktable.create.await_args.kwargs["data"]
    selected: Final = ("credential_name", "status", "error_message", "response_time_ms", "details", "checked_at")
    prisma.db.query_raw = AsyncMock(return_value=[{column: written[column] for column in selected}])

    assert await repository.latest_results() == (result,)
    assert (written["credential_name"], written["model_name"], written["checked_by"]) == (
        "openai-prod",
        "openai",
        "admin-user",
    )


@pytest.mark.asyncio
async def test_latest_dedups_per_credential_in_sql_and_reads_naive_timestamps_as_utc():
    prisma: Final = _prisma(
        [
            {
                "credential_name": "anthropic-main",
                "status": "healthy",
                "error_message": None,
                "response_time_ms": 10.0,
                "details": json.dumps({"kind": "model_list", "http_status": None}),
                "checked_at": "2026-11-12T10:00:00",
            },
            {
                "credential_name": "groq-main",
                "status": "untested",
                "error_message": "test model required",
                "response_time_ms": None,
                "details": {"kind": None, "http_status": None},
                "checked_at": "2026-11-12T11:00:00+01:00",
            },
        ]
    )

    results: Final = await CredentialTestRepository(prisma).latest_results()

    assert prisma.db.query_raw.await_args.args == (LATEST_CREDENTIAL_TESTS_SQL,)
    assert 'DISTINCT ON ("credential_name")' in LATEST_CREDENTIAL_TESTS_SQL
    assert '"checked_at" DESC' in LATEST_CREDENTIAL_TESTS_SQL
    assert [(r.credential_name, r.status, r.kind, r.error, r.checked_at) for r in results] == [
        ("anthropic-main", "healthy", "model_list", None, T0),
        ("groq-main", "untested", None, "test model required", T0),
    ]
