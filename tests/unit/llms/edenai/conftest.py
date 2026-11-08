import asyncio
import uuid

import pytest

import hangarllm
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER


@pytest.fixture
def eden_key(monkeypatch) -> str:
    monkeypatch.delenv("EDENAI_API_BASE", raising=False)
    monkeypatch.setenv("EDENAI_API_KEY", "eden-test-key")
    monkeypatch.setattr(hangarllm, "api_key", None)
    return "eden-test-key"


@pytest.fixture
def no_eden_key(monkeypatch) -> None:
    monkeypatch.delenv("EDENAI_API_KEY", raising=False)
    monkeypatch.setattr(hangarllm, "api_key", None)


class SpendCapture(CustomLogger):
    """Records the cost the spend logs would store for one call, matched by its call id."""

    def __init__(self, call_id: str):
        super().__init__()
        self.call_id = call_id
        self.costs: list[object] = []

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        if kwargs.get("hangarllm_call_id") == self.call_id:
            self.costs.append((kwargs.get("standard_logging_object") or {}).get("response_cost"))

    async def settle(self) -> None:
        await asyncio.sleep(0)
        await asyncio.wait_for(GLOBAL_LOGGING_WORKER.flush(), timeout=10.0)


@pytest.fixture
def spend_capture(monkeypatch) -> SpendCapture:
    capture = SpendCapture(call_id=f"eden-{uuid.uuid4()}")
    monkeypatch.setattr(hangarllm, "callbacks", [capture])
    return capture


@pytest.fixture
def httpx_transport(monkeypatch):
    """respx fakes httpx, so the async client must not sit on HangarLLM's default aiohttp transport."""
    monkeypatch.setattr(  # test-quality-ok: respx needs HTTPX enabled to fake the provider HTTP boundary.
        hangarllm,
        "disable_aiohttp_transport",
        True,
    )
    hangarllm.in_memory_llm_clients_cache.flush_cache()
    yield
    hangarllm.in_memory_llm_clients_cache.flush_cache()
