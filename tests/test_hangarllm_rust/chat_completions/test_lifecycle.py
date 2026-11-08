import asyncio
from typing import Final

import pytest

import hangarllm
from hangarllm.rust_bridge import _native, execution
from hangarllm.rust_bridge.public_call import NativeCall
from tests.test_hangarllm_rust.chat_completions.data import REQUEST
from tests.test_hangarllm_rust.support.callback_recorder import RecordingLogger
from tests.test_hangarllm_rust.support.recording_server import RecordingServer

pytestmark = pytest.mark.requires_rust_extension


@pytest.mark.asyncio
async def test_unstarted_call_has_no_provider_or_callback_effects(
    server: RecordingServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder: Final = RecordingLogger()
    server.expected_requests = 0
    monkeypatch.setattr(hangarllm, "ssl_verify", object())
    monkeypatch.setattr(hangarllm, "max_budget", 1.0)
    monkeypatch.setattr(hangarllm, "_current_cost", 2.0)
    kwargs: Final = {
        **REQUEST,
        "api_key": "test-key",
        "api_base": server.base_url,
        "callbacks": [recorder],
    }

    pending: Final = execution.asynchronous(_native.acompletion)(NativeCall(args=(), kwargs=kwargs, base={}))
    assert asyncio.iscoroutine(pending)
    pending.close()

    assert not server.requests
    assert not recorder.events
