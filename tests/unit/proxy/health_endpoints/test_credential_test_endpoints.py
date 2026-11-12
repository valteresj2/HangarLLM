import asyncio
import io
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, TypeAlias

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import JsonValue

import hangarllm
from hangarllm._logging import verbose_logger, verbose_proxy_logger, verbose_router_logger
from hangarllm.models.credential_test import CredentialTestResult
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.deps.database import get_database
from hangarllm.proxy.deps.repositories import get_credential_test_repository
from hangarllm.proxy.health_endpoints.credential_test_endpoints import (
    CredentialTestLimits,
    ProviderProbe,
    credential_test_limits,
    provider_probe,
    router,
)
from hangarllm.types.utils import CredentialItem

SECRET_KEY: Final = "sk-live-0123456789abcdefSECRET"
OPENAI_MODELS_URL: Final = "https://api.openai.com/v1/models"
MISTRAL_CHAT_URL: Final = "https://api.mistral.ai/v1/chat/completions"
T0: Final = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
SavedResult: TypeAlias = tuple[CredentialTestResult, str, str | None]


@dataclass
class InMemoryResultStore:
    saved: tuple[SavedResult, ...] = ()
    latest: tuple[CredentialTestResult, ...] = ()

    async def save_result(self, result: CredentialTestResult, provider: str, checked_by: str | None) -> None:
        self.saved = (*self.saved, (result, provider, checked_by))

    async def latest_results(self) -> tuple[CredentialTestResult, ...]:
        return self.latest


@dataclass
class PeakConcurrencyProbe:
    active: int = 0
    peak: int = 0
    calls: int = 0

    async def list_models(self, provider: str, values: Mapping[str, JsonValue]) -> None:
        self.active += 1
        self.calls += 1
        self.peak = max(self.peak, self.active)
        for _ in range(20):
            await asyncio.sleep(0)
        self.active -= 1

    async def complete(self, provider: str, model: str, values: Mapping[str, JsonValue]) -> None:
        raise AssertionError("no completion expected")


class HangingProbe:
    async def list_models(self, provider: str, values: Mapping[str, JsonValue]) -> None:
        await asyncio.Event().wait()

    async def complete(self, provider: str, model: str, values: Mapping[str, JsonValue]) -> None:
        await asyncio.Event().wait()


@dataclass
class Harness:
    app: FastAPI
    client: TestClient
    store: InMemoryResultStore
    monkeypatch: pytest.MonkeyPatch

    def as_role(self, role: HangarllmUserRoles) -> None:
        async def auth() -> UserAPIKeyAuth:
            return UserAPIKeyAuth(api_key="sk-caller", user_id="admin-user", user_role=role)

        self.app.dependency_overrides[user_api_key_auth] = auth

    def with_credentials(self, *credentials: CredentialItem) -> None:
        self.monkeypatch.setattr(hangarllm, "credential_list", list(credentials))

    def with_probe(self, probe: ProviderProbe) -> None:
        self.app.dependency_overrides[provider_probe] = lambda: probe

    def with_timeout(self, seconds: float) -> None:
        self.app.dependency_overrides[credential_test_limits] = lambda: CredentialTestLimits(timeout_seconds=seconds)

    def with_latest(self, *results: CredentialTestResult) -> None:
        self.store.latest = results

    def without_database(self) -> None:
        self.app.dependency_overrides[get_credential_test_repository] = lambda: None


def _credential(
    name: str, provider: str, *, source: str = "db", test_model: str | None = None, api_key: str = SECRET_KEY
) -> CredentialItem:
    info: Final = {"custom_llm_provider": provider, **({"test_model": test_model} if test_model else {})}
    return CredentialItem(
        credential_name=name, credential_values={"api_key": api_key}, credential_info=info, source=source
    )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    app: Final = FastAPI()
    app.include_router(router)
    store: Final = InMemoryResultStore()
    app.dependency_overrides[get_database] = lambda: None
    app.dependency_overrides[get_credential_test_repository] = lambda: store
    test_harness: Final = Harness(app=app, client=TestClient(app), store=store, monkeypatch=monkeypatch)
    test_harness.with_credentials()
    test_harness.as_role(HangarllmUserRoles.PROXY_ADMIN)
    yield test_harness


@pytest.fixture
def captured_logs() -> Iterator[io.StringIO]:
    stream: Final = io.StringIO()
    handler: Final = logging.StreamHandler(stream)
    loggers: Final = (verbose_logger, verbose_proxy_logger, verbose_router_logger, logging.getLogger())
    levels: Final = tuple(logger.level for logger in loggers)
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    yield stream
    for logger, level in zip(loggers, levels):
        logger.removeHandler(handler)
        logger.setLevel(level)


def _without_timing(result: Mapping[str, object]) -> Mapping[str, object]:
    return {key: value for key, value in result.items() if key not in ("latency_ms", "checked_at")}


class TestSavedCredential:
    def test_a_key_the_provider_accepts_is_healthy_and_stored(self, harness: Harness):
        harness.with_credentials(_credential("openai-prod", "OpenAI"))
        with respx.mock() as upstream:
            models: Final = upstream.get(OPENAI_MODELS_URL).respond(200, json={"data": [{"id": "gpt-4o-mini"}]})
            response: Final = harness.client.post("/health/credential_test", json={"credential_name": "openai-prod"})

        assert response.status_code == 200, response.text
        assert _without_timing(response.json()) == {
            "credential_name": "openai-prod",
            "status": "healthy",
            "kind": "model_list",
            "http_status": None,
            "error": None,
        }
        assert models.calls.last.request.headers["authorization"] == f"Bearer {SECRET_KEY}"
        assert [
            (result.credential_name, result.status, provider, by) for result, provider, by in harness.store.saved
        ] == [("openai-prod", "healthy", "openai", "admin-user")]

    def test_a_rejected_key_is_failing_with_the_provider_status_and_never_echoes_the_key(
        self, harness: Harness, captured_logs: io.StringIO
    ):
        harness.with_credentials(_credential("openai-prod", "OpenAI"))
        with respx.mock() as upstream:
            upstream.get(OPENAI_MODELS_URL).respond(
                401, json={"error": {"message": f"Incorrect API key provided: {SECRET_KEY}"}}
            )
            response: Final = harness.client.post("/health/credential_test", json={"credential_name": "openai-prod"})

        assert response.status_code == 200, response.text
        body: Final = response.json()
        assert (body["status"], body["kind"], body["http_status"]) == ("failing", "model_list", 401)
        assert body["error"]
        assert SECRET_KEY not in response.text
        assert SECRET_KEY not in captured_logs.getvalue()
        assert [result.http_status for result, _, _ in harness.store.saved] == [401]

    def test_a_provider_without_a_model_list_and_no_test_model_stays_untested(self, harness: Harness):
        harness.with_credentials(_credential("groq-main", "Groq"))
        with respx.mock() as upstream:
            response: Final = harness.client.post("/health/credential_test", json={"credential_name": "groq-main"})

        assert response.status_code == 200, response.text
        assert _without_timing(response.json()) == {
            "credential_name": "groq-main",
            "status": "untested",
            "kind": None,
            "http_status": None,
            "error": "test model required",
        }
        assert upstream.calls.call_count == 0

    def test_a_provider_without_a_model_list_runs_a_one_token_completion_on_the_test_model(self, harness: Harness):
        harness.with_credentials(_credential("mistral-main", "MistralAI", test_model="mistral-small-latest"))
        with respx.mock() as upstream:
            chat: Final = upstream.post(MISTRAL_CHAT_URL).respond(
                200,
                json={
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "created": 1_792_000_000,
                    "model": "mistral-small-latest",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "p"}, "finish_reason": "length"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )
            response: Final = harness.client.post("/health/credential_test", json={"credential_name": "mistral-main"})

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["kind"]) == ("healthy", "completion")
        assert chat.calls.last.request.headers["authorization"] == f"Bearer {SECRET_KEY}"
        request_body: Final = chat.calls.last.request.content.decode()
        assert '"mistral-small-latest"' in request_body
        assert '"max_tokens": 1' in request_body or '"max_completion_tokens": 1' in request_body

    def test_a_config_defined_credential_can_be_tested(self, harness: Harness):
        harness.with_credentials(_credential("from-config", "OpenAI", source="config"))
        with respx.mock() as upstream:
            upstream.get(OPENAI_MODELS_URL).respond(200, json={"data": []})
            response: Final = harness.client.post("/health/credential_test", json={"credential_name": "from-config"})

        assert response.status_code == 200, response.text
        assert (response.json()["credential_name"], response.json()["status"]) == ("from-config", "healthy")

    def test_an_unknown_credential_is_not_found(self, harness: Harness):
        response: Final = harness.client.post("/health/credential_test", json={"credential_name": "missing"})

        assert response.status_code == 404
        assert harness.store.saved == ()

    def test_a_test_that_outlives_its_timeout_fails_as_timeout(self, harness: Harness):
        harness.with_credentials(_credential("openai-prod", "OpenAI"))
        harness.with_probe(HangingProbe())
        harness.with_timeout(0.01)

        response: Final = harness.client.post("/health/credential_test", json={"credential_name": "openai-prod"})

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["error"]) == ("failing", "timeout")


class TestUnsavedCredential:
    def test_is_tested_with_the_given_values_and_stores_nothing(self, harness: Harness):
        with respx.mock() as upstream:
            models: Final = upstream.get(OPENAI_MODELS_URL).respond(401, json={"error": {"message": "bad key"}})
            response: Final = harness.client.post(
                "/health/credential_test",
                json={"provider": "OpenAI", "credential_values": {"api_key": SECRET_KEY}, "test_model": "gpt-4o-mini"},
            )

        assert response.status_code == 200, response.text
        body: Final = response.json()
        assert (body["credential_name"], body["status"], body["kind"], body["http_status"]) == (
            None,
            "failing",
            "model_list",
            401,
        )
        assert models.calls.last.request.headers["authorization"] == f"Bearer {SECRET_KEY}"
        assert harness.store.saved == ()

    def test_an_environment_reference_is_rejected(self, harness: Harness):
        with respx.mock() as upstream:
            response: Final = harness.client.post(
                "/health/credential_test",
                json={"provider": "OpenAI", "credential_values": {"api_key": "os.environ/OPENAI_API_KEY"}},
            )

        assert response.status_code == 400
        assert upstream.calls.call_count == 0


class TestBatch:
    def test_runs_at_most_the_concurrency_limit_at_once(self, harness: Harness):
        names: Final = tuple(f"openai-{index}" for index in range(12))
        harness.with_credentials(*(_credential(name, "OpenAI") for name in names))
        probe: Final = PeakConcurrencyProbe()
        harness.with_probe(probe)

        response: Final = harness.client.post("/health/credential_test/batch", json={"credential_names": list(names)})

        assert response.status_code == 200, response.text
        assert [result["credential_name"] for result in response.json()["results"]] == list(names)
        assert (probe.calls, probe.peak) == (12, 5)
        assert len(harness.store.saved) == 12

    def test_reports_each_credential_and_never_echoes_a_key(self, harness: Harness, captured_logs: io.StringIO):
        harness.with_credentials(
            _credential("openai-good", "OpenAI", api_key="sk-good-key-000"), _credential("openai-bad", "OpenAI")
        )
        with respx.mock() as upstream:
            upstream.get(OPENAI_MODELS_URL).mock(
                side_effect=lambda request: httpx.Response(
                    200 if request.headers["authorization"] == "Bearer sk-good-key-000" else 401,
                    json={"data": []} if "good" in request.headers["authorization"] else {"error": SECRET_KEY},
                )
            )
            response: Final = harness.client.post(
                "/health/credential_test/batch", json={"credential_names": ["openai-good", "openai-bad", "missing"]}
            )

        assert response.status_code == 200, response.text
        assert [(r["credential_name"], r["status"], r["http_status"]) for r in response.json()["results"]] == [
            ("openai-good", "healthy", None),
            ("openai-bad", "failing", 401),
            ("missing", "untested", None),
        ]
        assert SECRET_KEY not in response.text
        assert "sk-good-key-000" not in response.text
        assert SECRET_KEY not in captured_logs.getvalue()
        assert sorted(result.credential_name for result, _, _ in harness.store.saved) == ["openai-bad", "openai-good"]


class TestLatest:
    def test_returns_the_stored_results(self, harness: Harness):
        harness.with_latest(
            CredentialTestResult(
                credential_name="openai-prod",
                status="failing",
                kind="model_list",
                http_status=401,
                error="HTTP 401",
                latency_ms=12.0,
                checked_at=T0,
            )
        )

        response: Final = harness.client.get("/health/credential_test/latest")

        assert response.status_code == 200, response.text
        assert response.json() == {
            "results": [
                {
                    "credential_name": "openai-prod",
                    "status": "failing",
                    "kind": "model_list",
                    "http_status": 401,
                    "error": "HTTP 401",
                    "latency_ms": 12.0,
                    "checked_at": "2026-11-12T10:00:00Z",
                }
            ]
        }

    def test_without_a_database_is_empty(self, harness: Harness):
        harness.without_database()

        assert harness.client.get("/health/credential_test/latest").json() == {"results": []}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/health/credential_test", {"credential_name": "openai-prod"}),
        ("POST", "/health/credential_test/batch", {"credential_names": ["openai-prod"]}),
        ("GET", "/health/credential_test/latest", None),
    ],
)
@pytest.mark.parametrize(
    "role", [HangarllmUserRoles.INTERNAL_USER, HangarllmUserRoles.PROXY_ADMIN_VIEW_ONLY, HangarllmUserRoles.TEAM]
)
def test_a_non_admin_caller_is_rejected(harness: Harness, method: str, path: str, body: object, role):
    harness.with_credentials(_credential("openai-prod", "OpenAI"))
    harness.as_role(role)
    with respx.mock() as upstream:
        response: Final = harness.client.request(method, path, json=body)

    assert response.status_code == 403
    assert upstream.calls.call_count == 0
    assert harness.store.saved == ()
