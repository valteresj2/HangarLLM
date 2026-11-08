import asyncio
import importlib

import pytest

import hangarllm
from hangarllm.hangarllm_core_utils.llm_response_utils.get_headers import (
    _get_llm_provider_headers,
    get_response_headers,
    get_provider_request_id,
    provider_request_id_headers,
)
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome


def test_get_response_headers_empty():
    result = get_response_headers()
    assert result == {}, "Expected empty dictionary for no input"


def test_get_response_headers_with_openai_headers():
    """
    OpenAI headers are forwarded as is
    Other headers are prefixed with llm_provider-
    """
    input_headers = {
        "x-ratelimit-limit-requests": "100",
        "x-ratelimit-remaining-requests": "50",
        "x-ratelimit-limit-tokens": "1000",
        "x-ratelimit-remaining-tokens": "500",
        "other-header": "value",
    }
    expected_output = {
        "x-ratelimit-limit-requests": "100",
        "x-ratelimit-remaining-requests": "50",
        "x-ratelimit-limit-tokens": "1000",
        "x-ratelimit-remaining-tokens": "500",
        "llm_provider-x-ratelimit-limit-requests": "100",
        "llm_provider-x-ratelimit-remaining-requests": "50",
        "llm_provider-x-ratelimit-limit-tokens": "1000",
        "llm_provider-x-ratelimit-remaining-tokens": "500",
        "llm_provider-other-header": "value",
    }
    result = get_response_headers(input_headers)
    assert result == expected_output, "Unexpected output for OpenAI headers"


def test_get_response_headers_without_openai_headers():
    """
    Non-OpenAI headers are prefixed with llm_provider-
    """
    input_headers = {"custom-header-1": "value1", "custom-header-2": "value2"}
    expected_output = {
        "llm_provider-custom-header-1": "value1",
        "llm_provider-custom-header-2": "value2",
    }
    result = get_response_headers(input_headers)
    assert result == expected_output, "Unexpected output for non-OpenAI headers"


def test_get_llm_provider_headers():
    """
    If non OpenAI headers are already prefixed with llm_provider- they are not prefixed with llm_provider- again
    """
    input_headers = {
        "header1": "value1",
        "header2": "value2",
        "llm_provider-existing": "existing_value",
    }
    expected_output = {
        "llm_provider-header1": "value1",
        "llm_provider-header2": "value2",
        "llm_provider-existing": "existing_value",
    }
    result = _get_llm_provider_headers(input_headers)
    assert result == expected_output, "Unexpected output for _get_llm_provider_headers"


@pytest.mark.parametrize("header", ("request-id", "Request-Id", "x-request-id", "llm_provider-request-id"))
def test_native_clients_receive_the_provider_request_id(header: str) -> None:
    result = get_response_headers({header: "req_test", "unrelated": "value"})
    assert result["request-id"] == "req_test"
    assert get_provider_request_id(result) == "req_test"
    assert result["llm_provider-unrelated"] == "value"
    assert "unrelated" not in result


@pytest.mark.parametrize("headers", (None, {}, {"request-id": ""}, {"request-id": 42}))
def test_invalid_provider_request_ids_remain_absent(headers: object) -> None:
    assert get_provider_request_id(headers) is None


@pytest.mark.parametrize(
    ("headers", "expected"),
    (
        (
            {"X-Amzn-RequestId": "amzn-1", "retry-after": "7", "content-type": "text/event-stream"},
            {"x-amzn-requestid": "amzn-1"},
        ),
        (
            {"x-request-id": "req_1", "cf-ray": "ray-1", "x-ratelimit-remaining-requests": "0"},
            {"x-request-id": "req_1", "cf-ray": "ray-1"},
        ),
        ({"retry-after": "7"}, None),
        ({"x-request-id": 7, "request-id": None, "x-amzn-requestid": "amzn-2"}, {"x-amzn-requestid": "amzn-2"}),
        ({"x-amzn-requestid": "amzn-\u00fc", "x-request-id": "req_2"}, {"x-request-id": "req_2"}),
        ({}, None),
        (None, None),
    ),
)
def test_provider_request_id_headers_keeps_only_request_id_headers(
    headers: dict[str, object] | None, expected: dict[str, str] | None
) -> None:
    result = provider_request_id_headers(headers)
    assert (None if result is None else dict(result)) == expected


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
