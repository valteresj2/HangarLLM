import asyncio
import importlib
import re
from pathlib import Path
from typing import Final

import httpx
import httpx2
import pytest

import hangarllm
from tests._vcr_conftest_common import (
    detect_vcr_patch_leak,
    guard_vcr_patch_points,
    install_live_call_probe,
    record_vcr_outcome,
    restore_vcr_patch_points,
    rewound_new_episodes_cassette,
)

_ORIGINAL_MOCK_HANDLE_ASYNC_REQUEST: Final = httpx.MockTransport.handle_async_request
_ORIGINAL_HTTPX2_MOCK_HANDLE_ASYNC_REQUEST: Final = httpx2.MockTransport.handle_async_request


@pytest.fixture
def leaked_cassette_dir(tmp_path: Path):
    context: Final = rewound_new_episodes_cassette(tmp_path)
    context.__enter__()
    yield tmp_path
    context.__exit__(None, None, None)


def test_no_leak_when_no_cassette_is_active():
    assert detect_vcr_patch_leak() is None


def test_leaked_cassette_is_detected_named_and_restorable(leaked_cassette_dir: Path):
    leak: Final = detect_vcr_patch_leak()

    assert leak is not None
    assert {"httpx.MockTransport.handle_async_request", "aiohttp.client.ClientSession._request"} <= set(
        leak.patch_points
    )
    assert leak.cassette_paths == (str(leaked_cassette_dir / "rewound_owner.yaml"),)

    restore_vcr_patch_points()

    assert detect_vcr_patch_leak() is None
    assert httpx.MockTransport.handle_async_request is _ORIGINAL_MOCK_HANDLE_ASYNC_REQUEST


def test_leak_is_detected_on_every_transport_family_vcrpy_patches(leaked_cassette_dir: Path):
    leak: Final = detect_vcr_patch_leak()

    assert leak is not None
    assert "httpx2.MockTransport.handle_async_request" in leak.patch_points
    assert httpx2.MockTransport.handle_async_request is not _ORIGINAL_HTTPX2_MOCK_HANDLE_ASYNC_REQUEST

    restore_vcr_patch_points()

    assert httpx2.MockTransport.handle_async_request is _ORIGINAL_HTTPX2_MOCK_HANDLE_ASYNC_REQUEST


def test_guard_fails_the_leaking_test_and_restores_the_originals(request, leaked_cassette_dir: Path):
    with pytest.raises(pytest.fail.Exception, match=re.escape(request.node.nodeid)) as failure:
        guard_vcr_patch_points(request.node, teardown_failed=False)

    assert str(leaked_cassette_dir / "rewound_owner.yaml") in str(failure.value)
    assert detect_vcr_patch_leak() is None


def test_guard_restores_silently_when_the_teardown_already_failed(request, leaked_cassette_dir: Path):
    guard_vcr_patch_points(request.node, teardown_failed=True)

    assert detect_vcr_patch_leak() is None


@pytest.fixture(autouse=True)
def _vcr_outcome_gate(request, vcr):
    install_live_call_probe(request, vcr)
    yield
    record_vcr_outcome(request, vcr)


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown(event_loop):
    import hangarllm

    original_state = {}
    for attr in (
        "callbacks",
        "success_callback",
        "failure_callback",
        "_async_success_callback",
        "_async_failure_callback",
    ):
        if hasattr(hangarllm, attr):
            val = getattr(hangarllm, attr)
            original_state[attr] = val.copy() if val else []
    for attr in _SCALAR_DEFAULTS:
        if hasattr(hangarllm, attr):
            original_state[attr] = getattr(hangarllm, attr)
    from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

    asyncio.run(GLOBAL_LOGGING_WORKER.clear_queue())
    importlib.reload(hangarllm)
    asyncio.set_event_loop(event_loop)
    yield
    for attr, original_value in original_state.items():
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, original_value)
    pending = asyncio.all_tasks(event_loop)
    for task in pending:
        task.cancel()
    if pending:
        event_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


_SCALAR_DEFAULTS = {
    "num_retries": getattr(hangarllm, "num_retries", None),
    "set_verbose": getattr(hangarllm, "set_verbose", False),
    "cache": getattr(hangarllm, "cache", None),
    "allowed_fails": getattr(hangarllm, "allowed_fails", 3),
    "disable_aiohttp_transport": getattr(hangarllm, "disable_aiohttp_transport", False),
    "force_ipv4": getattr(hangarllm, "force_ipv4", False),
    "drop_params": getattr(hangarllm, "drop_params", None),
    "modify_params": getattr(hangarllm, "modify_params", False),
    "api_base": getattr(hangarllm, "api_base", None),
    "api_key": getattr(hangarllm, "api_key", None),
    "cohere_key": getattr(hangarllm, "cohere_key", None),
}
