# What is this?
## Unit Tests for guardrails config
import importlib
import os
import time
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

import hangarllm
import hangarllm.hangarllm_core_utils
import hangarllm.hangarllm_core_utils.hangarllm_logging
from hangarllm import completion
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.types.guardrails import BaseHangarllmParams, HangarllmParams
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome


class CustomLoggingIntegration(CustomLogger):
    def __init__(self) -> None:
        super().__init__()

    def logging_hook(self, kwargs: dict, result: Any, call_type: str) -> Tuple[dict, Any]:
        input: Optional[Any] = kwargs.get("input", None)
        messages: Optional[List] = kwargs.get("messages", None)
        if call_type == "completion":
            # assume input is of type messages
            if input is not None and isinstance(input, list):
                input[0]["content"] = "Hey, my name is [NAME]."
            if messages is not None and isinstance(messages, List):
                messages[0]["content"] = "Hey, my name is [NAME]."

            kwargs["input"] = input
            kwargs["messages"] = messages
        return kwargs, result


def test_guardrail_masking_logging_only():
    """
    Assert response is unmasked.

    Assert logged response is masked.
    """
    callback = CustomLoggingIntegration()

    with patch.object(callback, "log_success_event", new=MagicMock()) as mock_call:
        hangarllm.callbacks = [callback]
        messages = [{"role": "user", "content": "Hey, my name is Peter."}]
        response = completion(model="gpt-5-mini", messages=messages, mock_response="Hi Peter!")

        assert response.choices[0].message.content == "Hi Peter!"  # type: ignore

        time.sleep(3)
        mock_call.assert_called_once()

        assert mock_call.call_args.kwargs["kwargs"]["messages"][0]["content"] == "Hey, my name is [NAME]."


def test_guardrail_list_of_event_hooks():
    from hangarllm.integrations.custom_guardrail import CustomGuardrail
    from hangarllm.types.guardrails import GuardrailEventHooks

    cg = CustomGuardrail(guardrail_name="custom-guard", event_hook=["pre_call", "post_call"])

    data = {"model": "gpt-5-mini", "metadata": {"guardrails": ["custom-guard"]}}
    assert cg.should_run_guardrail(data=data, event_type=GuardrailEventHooks.pre_call)

    assert cg.should_run_guardrail(data=data, event_type=GuardrailEventHooks.post_call)

    assert not cg.should_run_guardrail(data=data, event_type=GuardrailEventHooks.during_call)


def test_guardrail_info_response():
    from hangarllm.types.guardrails import (
        GuardrailInfoResponse,
        HangarllmParams,
    )

    guardrail_info = GuardrailInfoResponse(
        guardrail_name="aporia-pre-guard",
        hangarllm_params=HangarllmParams(
            guardrail="aporia",
            mode="pre_call",
        ),
        guardrail_info={
            "guardrail_name": "aporia-pre-guard",
            "hangarllm_params": {
                "guardrail": "aporia",
                "mode": "always_on",
            },
        },
    )

    assert guardrail_info.hangarllm_params.default_on == False


@pytest.fixture(autouse=True)
def _vcr_outcome_gate(request, vcr):
    install_live_call_probe(request, vcr)
    yield
    record_vcr_outcome(request, vcr)


@pytest.fixture(scope="function", autouse=True)
def isolate_hangarllm_state():
    """
    Per-function isolation fixture.

    Saves and restores hangarllm callback/global state so tests don't leak
    side effects. Works safely under pytest-xdist parallel execution.
    """
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
    for attr in ("set_verbose", "cache", "num_retries"):
        if hasattr(hangarllm, attr):
            original_state[attr] = getattr(hangarllm, attr)
    if hasattr(hangarllm, "in_memory_llm_clients_cache"):
        hangarllm.in_memory_llm_clients_cache.flush_cache()
    for attr in ("success_callback", "failure_callback", "_async_success_callback", "_async_failure_callback"):
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, [])
    yield
    if hasattr(hangarllm, "in_memory_llm_clients_cache"):
        hangarllm.in_memory_llm_clients_cache.flush_cache()
    for attr, original_value in original_state.items():
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, original_value)


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """
    Module-scoped setup. Reloads hangarllm only in single-process mode
    (skipped under xdist to avoid cross-worker interference).
    """
    import hangarllm

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", None)
    if worker_id is None:
        importlib.reload(hangarllm)
        try:
            if hasattr(hangarllm, "proxy") and hasattr(hangarllm.proxy, "proxy_server"):
                import hangarllm.proxy.proxy_server

                importlib.reload(hangarllm.proxy.proxy_server)
        except Exception as e:
            print(f"Error reloading hangarllm.proxy.proxy_server: {e}")
        if hasattr(hangarllm, "in_memory_llm_clients_cache"):
            hangarllm.in_memory_llm_clients_cache.flush_cache()
    yield


@pytest.mark.parametrize("blank", ["", "   "])
def test_hangarllm_params_treats_blank_values_as_unset(blank: str) -> None:
    """
    Regression: `os.environ/X` with X exported blank resolves to "", which pydantic rejected on
    bool fields (default_on, mask_request_content, fail_on_error), so the guardrail was dropped at
    boot. Blank now means unset, so the field keeps the same default as when it is omitted.
    """
    with_blank_values = HangarllmParams(
        guardrail="presidio",
        mode="pre_call",
        default_on=blank,
        mask_request_content=blank,
        api_key=blank,
    )
    omitted = HangarllmParams(guardrail="presidio", mode="pre_call")
    assert with_blank_values.model_dump() == omitted.model_dump()

    assert BaseHangarllmParams(fail_on_error=blank).model_dump() == BaseHangarllmParams().model_dump()


@pytest.mark.parametrize(("configured", "loaded"), [("2", 2), (2, 2), ("0", 0), (5, 5), ("", None)])
def test_num_retries_loads_the_dashboard_string_and_blank_means_unset(configured: object, loaded: int | None) -> None:
    assert (
        HangarllmParams(guardrail="generic_guardrail_api", mode="pre_call", num_retries=configured).num_retries == loaded
    )


@pytest.mark.parametrize("configured", [-1, 6, "1.5", "twice"])
def test_num_retries_rejects_values_that_are_not_a_retry_count(configured: object) -> None:
    with pytest.raises(ValidationError, match="num_retries"):
        HangarllmParams(guardrail="generic_guardrail_api", mode="pre_call", num_retries=configured)
