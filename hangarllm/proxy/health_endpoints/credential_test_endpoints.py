import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Final, Protocol

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ConfigDict, Field, JsonValue, TypeAdapter

import hangarllm
from hangarllm._logging import verbose_proxy_logger
from hangarllm.models.credential_test import CredentialTestKind, CredentialTestResult, CredentialTestStore
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.common_utils.credential_hydration import (
    hydrate_named_credential_authoritative,
    stored_credential_provider,
)
from hangarllm.proxy.deps.database import DatabaseDep
from hangarllm.proxy.deps.repositories import CredentialTestRepositoryDep
from hangarllm.proxy.public_endpoints.public_endpoints import provider_create_fields
from hangarllm.types.llms.base import HangarLLMBaseModel
from hangarllm.types.utils import LlmProviders

router: Final = APIRouter()

MODEL_LIST_PROVIDERS: Final = frozenset(
    {"openai", "anthropic", "gemini", "xai", "baseten", "bedrock", "hosted_vllm", "lemonade", "hangarllm_proxy"}
)
TEST_MODEL_REQUIRED: Final = "test model required"
_ERROR_MAX_LENGTH: Final = 200
_MIN_REDACTED_LENGTH: Final = 4
_REDACTED: Final = "[REDACTED]"
_STATUS_IN_MESSAGE: Final = re.compile(r"(?:status code|error code|HTTP):?\s*(\d{3})\b", re.IGNORECASE)
_CREDENTIAL_VALUES: Final = TypeAdapter(dict[str, JsonValue])


class SavedCredentialTest(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    credential_name: str = Field(description="Name of a stored or config defined credential to test.")


class UnsavedCredentialTest(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(description="Catalog provider key, such as OpenAI, or a hangarllm provider id.")
    credential_values: Mapping[str, JsonValue]
    test_model: str | None = Field(
        default=None, description="Model used for a one token completion when the provider has no model list call."
    )


class CredentialTestBatchRequest(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    credential_names: tuple[str, ...]


class CredentialTestResults(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[CredentialTestResult, ...]


@dataclass(frozen=True, slots=True)
class CredentialTestLimits:
    concurrency: int = 5
    timeout_seconds: float = 20.0


@dataclass(frozen=True, slots=True)
class CredentialUnderTest:
    credential_name: str | None
    provider: str | None
    values: Mapping[str, JsonValue]
    test_model: str | None


class ProviderProbe(Protocol):
    async def list_models(self, provider: str, values: Mapping[str, JsonValue]) -> None: ...

    async def complete(self, provider: str, model: str, values: Mapping[str, JsonValue]) -> None: ...


class LiveProviderProbe:
    async def list_models(self, provider: str, values: Mapping[str, JsonValue]) -> None:
        from hangarllm.utils import ProviderConfigManager

        provider_config: Final = ProviderConfigManager.get_provider_model_info(
            model=None, provider=LlmProviders(provider)
        )
        if provider_config is None:
            raise ValueError(f"{provider} has no model list call")
        await asyncio.to_thread(provider_config.discover_models, dict(values))

    async def complete(self, provider: str, model: str, values: Mapping[str, JsonValue]) -> None:
        await hangarllm.acompletion(
            model=model if model.startswith(f"{provider}/") else f"{provider}/{model}",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            **values,
        )


def provider_probe() -> ProviderProbe:
    return LiveProviderProbe()


def credential_test_limits() -> CredentialTestLimits:
    return CredentialTestLimits()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _credential_test_admin(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> UserAPIKeyAuth:
    if user_api_key_dict.user_role != HangarllmUserRoles.PROXY_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only proxy admins can test credentials.")
    return user_api_key_dict


def resolve_router_provider(provider: object) -> str | None:
    if not isinstance(provider, str):
        return None
    catalog_match: Final = next(
        (entry.hangarllm_provider for entry in provider_create_fields() if entry.provider == provider), None
    )
    return catalog_match or stored_credential_provider(provider)


def _secret_strings(values: Mapping[str, JsonValue]) -> tuple[str, ...]:
    flattened: Final = tuple(
        json.dumps(value) if isinstance(value, (dict, list)) else value for value in values.values()
    )
    return tuple(value for value in flattened if isinstance(value, str) and len(value) >= _MIN_REDACTED_LENGTH)


def _redacted_message(error: BaseException, values: Mapping[str, JsonValue]) -> str:
    message: Final = " ".join(str(error).split())
    secrets: Final = sorted(_secret_strings(values), key=len, reverse=True)
    redacted: Final = re.sub("|".join(map(re.escape, secrets)), _REDACTED, message) if secrets else message
    return redacted[:_ERROR_MAX_LENGTH] or type(error).__name__


def _http_status(error: BaseException) -> int | None:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code
    status_code: Final[object] = getattr(error, "status_code", None)
    if isinstance(status_code, int) and 100 <= status_code <= 599:
        return status_code
    match: Final = _STATUS_IN_MESSAGE.search(str(error))
    return int(match.group(1)) if match is not None else None


def _error_chain(error: BaseException) -> Iterator[BaseException]:
    yield error
    linked: Final = error.__cause__ or error.__context__
    if linked is not None:
        yield from _error_chain(linked)


def _failure_error(error: BaseException, values: Mapping[str, JsonValue]) -> tuple[int | None, str]:
    chain: Final = tuple(_error_chain(error))
    if any(isinstance(link, (TimeoutError, httpx.TimeoutException, hangarllm.Timeout)) for link in chain):
        return None, "timeout"
    if any(isinstance(link, httpx.TransportError) for link in chain):
        return None, "network"
    return _http_status(error), _redacted_message(error, values)


def _probe_call(
    credential: CredentialUnderTest, provider: str, probe: ProviderProbe
) -> tuple[CredentialTestKind, Callable[[], Awaitable[None]]] | None:
    if provider in MODEL_LIST_PROVIDERS:
        return "model_list", lambda: probe.list_models(provider, credential.values)
    if credential.test_model:
        test_model: Final = credential.test_model
        return "completion", lambda: probe.complete(provider, test_model, credential.values)
    return None


async def run_credential_test(
    credential: CredentialUnderTest, probe: ProviderProbe, limits: CredentialTestLimits, now: datetime
) -> CredentialTestResult:
    untested: Final = CredentialTestResult(
        credential_name=credential.credential_name,
        status="untested",
        kind=None,
        http_status=None,
        error=None,
        latency_ms=None,
        checked_at=now,
    )
    if credential.provider is None:
        return untested.model_copy(update={"error": "unknown provider"})
    call: Final = _probe_call(credential, credential.provider, probe)
    if call is None:
        return untested.model_copy(update={"error": TEST_MODEL_REQUIRED})
    kind, run = call
    started: Final = time.perf_counter()
    try:
        await asyncio.wait_for(run(), timeout=limits.timeout_seconds)
    except Exception as error:  # noqa: BLE001  # every provider failure is reported as a failing result
        http_status, message = _failure_error(error, credential.values)
        verbose_proxy_logger.debug(
            "Credential test of %s failed with HTTP status %s", credential.credential_name, http_status
        )
        return untested.model_copy(
            update={
                "status": "failing",
                "kind": kind,
                "http_status": http_status,
                "error": message,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        )
    return untested.model_copy(
        update={"status": "healthy", "kind": kind, "latency_ms": (time.perf_counter() - started) * 1000}
    )


async def _saved_credential(credential_name: str, database: DatabaseDep) -> CredentialUnderTest | None:
    credential: Final = await hydrate_named_credential_authoritative(
        credential_name, None if database is None else database.prisma
    )
    if credential is None:
        return None
    info: Final = _CREDENTIAL_VALUES.validate_python(credential.credential_info)
    test_model: Final = info.get("test_model")
    return CredentialUnderTest(
        credential_name=credential_name,
        provider=resolve_router_provider(info.get("custom_llm_provider")),
        values=_CREDENTIAL_VALUES.validate_python(credential.credential_values),
        test_model=test_model if isinstance(test_model, str) and test_model else None,
    )


def _unsaved_credential(request: UnsavedCredentialTest) -> CredentialUnderTest:
    if '"os.environ/' in json.dumps(dict(request.credential_values)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Environment variable references are not permitted in request parameters."},
        )
    return CredentialUnderTest(
        credential_name=None,
        provider=resolve_router_provider(request.provider),
        values=request.credential_values,
        test_model=request.test_model,
    )


async def _test_and_store(
    credential: CredentialUnderTest,
    probe: ProviderProbe,
    limits: CredentialTestLimits,
    store: CredentialTestStore | None,
    checked_by: str | None,
) -> CredentialTestResult:
    test_result: Final = await run_credential_test(credential, probe, limits, utc_now())
    if store is not None and credential.credential_name is not None:
        await store.save_result(test_result, provider=credential.provider or "", checked_by=checked_by)
    return test_result


@router.post(
    "/health/credential_test",
    tags=["health"],
    response_model=CredentialTestResult,
)
async def test_credential(
    request: SavedCredentialTest | UnsavedCredentialTest,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(_credential_test_admin)],
    database: DatabaseDep,
    store: CredentialTestRepositoryDep,
    probe: Annotated[ProviderProbe, Depends(provider_probe)],
    limits: Annotated[CredentialTestLimits, Depends(credential_test_limits)],
) -> CredentialTestResult:
    """
    Test one credential, saved or not, by listing the provider's models or by a one token completion with the
    credential's test model. A saved credential's result is stored. Key values never appear in the response.
    """
    if isinstance(request, UnsavedCredentialTest):
        return await run_credential_test(_unsaved_credential(request), probe, limits, utc_now())
    credential: Final = await _saved_credential(request.credential_name, database)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    return await _test_and_store(credential, probe, limits, store, user_api_key_dict.user_id)


@router.post(
    "/health/credential_test/batch",
    tags=["health"],
    response_model=CredentialTestResults,
)
async def test_credentials_batch(
    request: CredentialTestBatchRequest,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(_credential_test_admin)],
    database: DatabaseDep,
    store: CredentialTestRepositoryDep,
    probe: Annotated[ProviderProbe, Depends(provider_probe)],
    limits: Annotated[CredentialTestLimits, Depends(credential_test_limits)],
) -> CredentialTestResults:
    """
    Test saved credentials, a few at a time with a timeout per test, and store each result.
    """
    semaphore: Final = asyncio.Semaphore(limits.concurrency)

    async def test_one(credential_name: str) -> CredentialTestResult:
        async with semaphore:
            credential: Final = await _saved_credential(credential_name, database)
            if credential is None:
                return CredentialTestResult(
                    credential_name=credential_name,
                    status="untested",
                    kind=None,
                    http_status=None,
                    error="credential not found",
                    latency_ms=None,
                    checked_at=utc_now(),
                )
            return await _test_and_store(credential, probe, limits, store, user_api_key_dict.user_id)

    return CredentialTestResults(results=tuple(await asyncio.gather(*map(test_one, request.credential_names))))


@router.get(
    "/health/credential_test/latest",
    tags=["health"],
    response_model=CredentialTestResults,
)
async def latest_credential_tests(
    _: Annotated[UserAPIKeyAuth, Depends(_credential_test_admin)],
    store: CredentialTestRepositoryDep,
) -> CredentialTestResults:
    """
    The newest stored test result of every saved credential.
    """
    return CredentialTestResults(results=() if store is None else await store.latest_results())
