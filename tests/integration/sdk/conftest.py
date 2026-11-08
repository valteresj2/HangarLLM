from collections.abc import AsyncIterator
from typing import Final

import pytest
import pytest_asyncio

import hangarllm
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

CALLBACK_LISTS: Final = (
    "callbacks",
    "success_callback",
    "failure_callback",
    "input_callback",
    "_async_success_callback",
    "_async_failure_callback",
    "_async_input_callback",
)


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def isolate_hangarllm_callback_lists(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    for name in CALLBACK_LISTS:
        monkeypatch.setattr(hangarllm, name, list(getattr(hangarllm, name)))
    try:
        yield
    finally:
        await GLOBAL_LOGGING_WORKER.flush()
        await GLOBAL_LOGGING_WORKER.stop()
