import asyncio
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Thread
from typing import Final, Literal

import pytest

import hangarllm
from hangarllm import Router
from hangarllm import utils as hangarllm_utils_module
from hangarllm.caching.caching import DualCache
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
from hangarllm.llms.bedrock.base_aws_llm import BaseAWSLLM
from tests.unit import conftest as unit_harness

CANARY_MODEL = "conftest-isolation-canary-model"


@dataclass(slots=True)
class _LoggingOwner:
    current: str = "original-test"
    delivered: tuple[str, ...] = ()

    async def deliver(self) -> None:
        self.delivered = (*self.delivered, self.current)


@pytest.mark.parametrize("loop_state", ("stopped", "running", "closed"))
def test_queued_logging_finishes_under_its_original_owner(loop_state: Literal["stopped", "running", "closed"]) -> None:
    owner: Final = _LoggingOwner()
    loop: Final = asyncio.new_event_loop()

    async def enqueue() -> None:
        GLOBAL_LOGGING_WORKER._ensure_queue()
        GLOBAL_LOGGING_WORKER.enqueue(owner.deliver())

    thread: Final = Thread(target=loop.run_forever) if loop_state == "running" else None
    if thread is not None:
        thread.start()
        asyncio.run_coroutine_threadsafe(enqueue(), loop).result()
    else:
        loop.run_until_complete(enqueue())
    if loop_state == "closed":
        loop.close()
    try:
        unit_harness._flush_completed_test_logging()
        owner.current = "next-test"
        assert owner.delivered == ("original-test",)
    finally:
        if thread is not None:
            asyncio.run_coroutine_threadsafe(GLOBAL_LOGGING_WORKER.stop(), loop).result()
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
        elif not loop.is_closed():
            loop.run_until_complete(GLOBAL_LOGGING_WORKER.stop())
        if not loop.is_closed():
            loop.close()


def test_dequeued_logging_finishes_under_its_original_owner() -> None:
    owner: Final = _LoggingOwner()

    async def enqueue() -> None:
        GLOBAL_LOGGING_WORKER.ensure_initialized_and_enqueue(owner.deliver())

    asyncio.run(enqueue())
    assert GLOBAL_LOGGING_WORKER._queue is not None
    assert GLOBAL_LOGGING_WORKER._queue.empty()
    assert owner.delivered == ()
    unit_harness._flush_completed_test_logging()
    owner.current = "next-test"
    assert owner.delivered == ("original-test",)


class _CanaryRouterHolder:
    router: Router | None = None


def test_register_model_ledger_entry_is_scoped_to_this_test():
    hangarllm.register_model({CANARY_MODEL: {"hangarllm_provider": "openai", "input_cost_per_token": 0.001}})
    assert CANARY_MODEL in hangarllm_utils_module._runtime_registered_model_cost


def test_register_model_ledger_entry_was_rolled_back():
    assert CANARY_MODEL not in hangarllm_utils_module._runtime_registered_model_cost


def test_register_model_catalog_writes_are_scoped_to_this_test():
    hangarllm.register_model(
        {
            CANARY_MODEL: {"hangarllm_provider": "openai", "mode": "chat", "input_cost_per_token": 0.001},
            "collection-isolation-ledger": {"input_cost_per_token": 0.5},
        }
    )
    assert CANARY_MODEL in hangarllm.model_cost
    assert CANARY_MODEL in hangarllm.open_ai_chat_completion_models
    assert CANARY_MODEL in hangarllm.models_by_provider["openai"]
    assert hangarllm.model_cost["collection-isolation-ledger"]["input_cost_per_token"] == 0.5


def test_register_model_catalog_writes_were_rolled_back():
    assert CANARY_MODEL not in hangarllm.model_cost
    assert CANARY_MODEL not in hangarllm.open_ai_chat_completion_models
    assert CANARY_MODEL not in hangarllm.models_by_provider["openai"]
    assert hangarllm.model_cost["collection-isolation-ledger"]["input_cost_per_token"] == 0.001


def test_live_router_membership_is_scoped_to_this_test():
    _CanaryRouterHolder.router = Router(
        model_list=[
            {
                "model_name": "conftest-isolation-canary-router",
                "hangarllm_params": {"model": "openai/conftest-isolation-canary-backend", "api_key": "sk-canary"},
            }
        ]
    )
    assert _CanaryRouterHolder.router._core._hosted in unit_harness.live_router_registries


def test_live_router_membership_was_rolled_back():
    assert _CanaryRouterHolder.router is not None
    assert _CanaryRouterHolder.router._core._hosted not in unit_harness.live_router_registries


def test_aws_cache_reset_sees_new_handlers_and_replaced_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    module: Final = unit_harness.importlib.import_module("hangarllm.files.main")
    handler: Final = BaseAWSLLM()
    first_cache: Final = DualCache()
    handler.iam_cache = first_cache
    monkeypatch.setattr(module, "unit_reset_canary", handler, raising=False)
    first_cache.set_cache("unit-reset-key", "first-secret")
    unit_harness._reset_aws_auth_caches()
    assert first_cache.get_cache("unit-reset-key") is None
    second_cache: Final = DualCache()
    handler.iam_cache = second_cache
    second_cache.set_cache("unit-reset-key", "second-secret")
    unit_harness._reset_aws_auth_caches()
    assert second_cache.get_cache("unit-reset-key") is None


def test_aws_cache_reset_sees_a_replaced_module(monkeypatch: pytest.MonkeyPatch) -> None:
    name: Final = "hangarllm.files.main"
    original_module: Final = unit_harness.importlib.import_module(name)
    package: Final = unit_harness.importlib.import_module("hangarllm.files")
    monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(package, "main", original_module)
    module: Final = unit_harness.importlib.import_module(name)
    handler: Final = BaseAWSLLM()
    cache: Final = DualCache()
    handler.iam_cache = cache
    monkeypatch.setattr(module, "unit_reset_canary", handler, raising=False)
    cache.set_cache("unit-reset-key", "module-secret")
    unit_harness._reset_aws_auth_caches()
    assert cache.get_cache("unit-reset-key") is None


@pytest.fixture(scope="module", autouse=True)
def registered_collection_models() -> Iterator[None]:
    original_registrations: Final = dict(hangarllm_utils_module._runtime_registered_model_cost)
    original_routers: Final = frozenset(unit_harness.live_router_registries)
    hangarllm.register_model(
        {"collection-isolation-ledger": {"hangarllm_provider": "openai", "input_cost_per_token": 0.001}}
    )
    collection_router: Final = Router(
        model_list=[
            {
                "model_name": "collection-isolation-router",
                "hangarllm_params": {"model": "openai/collection-isolation-backend", "api_key": "sk-canary"},
            }
        ]
    )
    yield
    hangarllm_utils_module._runtime_registered_model_cost.clear()
    hangarllm_utils_module._runtime_registered_model_cost.update(original_registrations)
    unit_harness.live_router_registries.discard(collection_router._core._hosted)
    unit_harness.live_router_registries.update(original_routers)


def test_collection_model_metadata_is_not_replayed_into_a_test_catalog() -> None:
    from hangarllm.hangarllm_core_utils.get_model_cost_map import adopt_model_cost_map

    catalog: Final = {"unit-test-catalog-model": {"hangarllm_provider": "openai", "input_cost_per_token": 0.001}}
    adopt_model_cost_map(catalog)
    assert "collection-isolation-ledger" not in hangarllm.model_cost
    assert "collection-isolation-router" not in hangarllm.model_cost
    assert "unit-test-catalog-model" in hangarllm.model_cost
