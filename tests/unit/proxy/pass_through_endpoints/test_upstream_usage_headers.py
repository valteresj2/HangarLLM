from typing import Final

import httpx
import pytest

from hangarllm.constants import MAX_SPEND_LOG_MODEL_NAME_LENGTH
from hangarllm.integrations.otel.model.semconv import PASSTHROUGH_OPERATION_KEY, GenAIOperation
from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as HangarLLMLoggingObj
from hangarllm.proxy.pass_through_endpoints.upstream_usage_headers import (
    UpstreamReportedUsage,
    apply_upstream_reported_model,
    apply_upstream_reported_operation,
    apply_upstream_reported_usage,
    has_upstream_reported_usage,
    parse_upstream_reported_model,
    parse_upstream_reported_usage,
)
from hangarllm.types.utils import Usage


def _headers(**values: str) -> httpx.Headers:
    return httpx.Headers(values)


def test_parse_reads_both_totals():
    reported = parse_upstream_reported_usage(
        _headers(
            **{
                "x-hangarllm-response-cost": "0.000415",
                "x-hangarllm-total-tokens": "1874",
            }
        )
    )

    assert reported == UpstreamReportedUsage(response_cost=0.000415, total_tokens=1874)


def test_parse_returns_none_when_upstream_does_not_speak_the_contract():
    assert parse_upstream_reported_usage(_headers(**{"content-type": "application/json"})) is None


def test_parse_accepts_explicit_zero_totals():
    reported = parse_upstream_reported_usage(
        _headers(**{"x-hangarllm-response-cost": "0", "x-hangarllm-total-tokens": "0"})
    )

    assert reported == UpstreamReportedUsage(response_cost=0.0, total_tokens=0)


@pytest.mark.parametrize(
    "raw_cost",
    ["not-a-number", "-0.5", "nan", "inf", ""],
)
def test_parse_rejects_unusable_cost_but_keeps_tokens(raw_cost: str):
    reported = parse_upstream_reported_usage(
        _headers(**{"x-hangarllm-response-cost": raw_cost, "x-hangarllm-total-tokens": "12"})
    )

    assert reported == UpstreamReportedUsage(response_cost=None, total_tokens=12)


@pytest.mark.parametrize("raw_tokens", ["1.5", "twelve", "-3", ""])
def test_parse_rejects_unusable_tokens_but_keeps_cost(raw_tokens: str):
    reported = parse_upstream_reported_usage(
        _headers(**{"x-hangarllm-response-cost": "1.25", "x-hangarllm-total-tokens": raw_tokens})
    )

    assert reported == UpstreamReportedUsage(response_cost=1.25, total_tokens=None)


def test_parse_reports_missing_counterpart_header():
    assert parse_upstream_reported_usage(_headers(**{"x-hangarllm-response-cost": "2.5"})) == UpstreamReportedUsage(
        response_cost=2.5, total_tokens=None
    )
    assert parse_upstream_reported_usage(_headers(**{"x-hangarllm-total-tokens": "7"})) == UpstreamReportedUsage(
        response_cost=None, total_tokens=7
    )


def _logging_obj() -> HangarLLMLoggingObj:
    logging_obj = HangarLLMLoggingObj(
        model="unknown",
        messages=[{"role": "user", "content": "x"}],
        stream=False,
        call_type="pass_through_endpoint",
        start_time=None,
        hangarllm_call_id="test-call-id",
        function_id="1",
    )
    return logging_obj


def test_apply_records_reported_totals():
    logging_obj = _logging_obj()

    reported = apply_upstream_reported_usage(
        logging_obj=logging_obj,
        headers=_headers(
            **{
                "x-hangarllm-response-cost": "0.000415",
                "x-hangarllm-total-tokens": "1874",
            }
        ),
    )

    assert reported is not None
    assert logging_obj.model_call_details["response_cost"] == 0.000415
    assert logging_obj.model_call_details["combined_usage_object"] == Usage(total_tokens=1874)


def test_apply_leaves_hangarllm_derived_values_alone_when_upstream_is_silent():
    logging_obj = _logging_obj()
    logging_obj.model_call_details["response_cost"] = 9.99
    logging_obj.model_call_details["combined_usage_object"] = Usage(total_tokens=42)

    assert apply_upstream_reported_usage(logging_obj=logging_obj, headers=_headers()) is None
    assert logging_obj.model_call_details["response_cost"] == 9.99
    assert logging_obj.model_call_details["combined_usage_object"] == Usage(total_tokens=42)


def test_apply_only_overwrites_what_upstream_reported():
    """A target that reports cost but not tokens must not zero out the token
    count HangarLLM derived from the response body itself."""
    logging_obj = _logging_obj()
    logging_obj.model_call_details["response_cost"] = 9.99
    logging_obj.model_call_details["combined_usage_object"] = Usage(total_tokens=42)

    apply_upstream_reported_usage(
        logging_obj=logging_obj,
        headers=_headers(**{"x-hangarllm-response-cost": "0.5"}),
    )

    assert logging_obj.model_call_details["response_cost"] == 0.5
    assert logging_obj.model_call_details["combined_usage_object"] == Usage(total_tokens=42)


@pytest.mark.parametrize(
    ("raw_model", "expected"),
    [
        ("support-summarizer", "support-summarizer"),
        ("  support-summarizer \t", "support-summarizer"),
        ("", None),
        ("   ", None),
    ],
)
def test_parse_reads_reported_model_and_treats_blank_as_absent(raw_model: str, expected: str | None):
    assert parse_upstream_reported_model(_headers(**{"x-hangarllm-upstream-model": raw_model})) == expected


def test_parse_returns_no_model_when_upstream_sends_none():
    assert parse_upstream_reported_model(_headers(**{"x-hangarllm-response-cost": "0.5"})) is None


def test_parse_uses_the_first_value_of_a_repeated_model_header():
    headers: Final = httpx.Headers(
        [("x-hangarllm-upstream-model", "support-summarizer"), ("x-hangarllm-upstream-model", "other")]
    )

    assert parse_upstream_reported_model(headers) == "support-summarizer"


@pytest.mark.parametrize(
    ("raw_model", "expected"),
    [
        ("m" * 5000, "m" * MAX_SPEND_LOG_MODEL_NAME_LENGTH),
        ("m" * MAX_SPEND_LOG_MODEL_NAME_LENGTH, "m" * MAX_SPEND_LOG_MODEL_NAME_LENGTH),
        ("m" * (MAX_SPEND_LOG_MODEL_NAME_LENGTH - 1) + " tail", "m" * (MAX_SPEND_LOG_MODEL_NAME_LENGTH - 1)),
    ],
    ids=["over_limit", "at_limit", "cut_lands_on_a_space"],
)
def test_parse_cuts_a_long_model_name_to_the_spend_log_limit(raw_model: str, expected: str):
    assert parse_upstream_reported_model(_headers(**{"x-hangarllm-upstream-model": raw_model})) == expected


def _logging_obj_for_model(model: str) -> HangarLLMLoggingObj:
    logging_obj: Final = _logging_obj()
    logging_obj.update_environment_variables(
        model=model, user="unknown", optional_params={}, hangarllm_params={}, call_type="pass_through_endpoint"
    )
    return logging_obj


def test_apply_model_replaces_the_request_model():
    logging_obj: Final = _logging_obj_for_model("gpt-4o")

    reported: Final = apply_upstream_reported_model(
        logging_obj=logging_obj,
        headers=_headers(**{"x-hangarllm-upstream-model": "support-summarizer"}),
    )

    assert reported == "support-summarizer"
    assert (logging_obj.model, logging_obj.model_call_details["model"]) == ("support-summarizer", "support-summarizer")


def test_apply_model_leaves_request_model_alone_when_header_is_blank():
    logging_obj: Final = _logging_obj_for_model("gpt-4o")

    assert (
        apply_upstream_reported_model(logging_obj=logging_obj, headers=_headers(**{"x-hangarllm-upstream-model": " "}))
        is None
    )
    assert (logging_obj.model, logging_obj.model_call_details["model"]) == ("gpt-4o", "gpt-4o")


def test_model_header_alone_does_not_make_the_upstream_own_the_cost():
    """The model name is a label: without a cost or token header the request
    must still fall back to cost_per_request, not be recorded at 0."""
    logging_obj: Final = _logging_obj()
    headers: Final = _headers(**{"x-hangarllm-upstream-model": "support-summarizer"})

    apply_upstream_reported_usage(logging_obj=logging_obj, headers=headers)
    apply_upstream_reported_model(logging_obj=logging_obj, headers=headers)

    assert has_upstream_reported_usage(logging_obj) is False
    assert "response_cost" not in logging_obj.model_call_details


@pytest.mark.parametrize("operation", [GenAIOperation.RETRIEVAL, GenAIOperation.EMBEDDINGS])
def test_apply_operation_records_the_operation_the_upstream_named(operation: GenAIOperation) -> None:
    logging_obj: Final = _logging_obj()

    apply_upstream_reported_operation(logging_obj, _headers(**{"x-hangarllm-operation-name": operation.value}))

    assert logging_obj.model_call_details[PASSTHROUGH_OPERATION_KEY] is operation


@pytest.mark.parametrize(
    "headers",
    [{}, {"x-hangarllm-operation-name": "summarize"}, {"x-hangarllm-operation-name": "Retrieval"}],
)
def test_apply_operation_ignores_a_missing_or_unknown_name(headers: dict[str, str]) -> None:
    logging_obj: Final = _logging_obj()

    apply_upstream_reported_operation(logging_obj, _headers(**headers))

    assert PASSTHROUGH_OPERATION_KEY not in logging_obj.model_call_details
