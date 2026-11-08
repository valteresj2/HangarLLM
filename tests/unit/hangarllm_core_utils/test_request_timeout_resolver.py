"""Unit tests for hangarllm.hangarllm_core_utils.request_timeout_resolver.

The resolver decides whether ``hangarllm.request_timeout`` was *explicitly configured*
(env REQUEST_TIMEOUT / hangarllm_settings, or a non-default runtime value) versus left
at the package default. This is what lets request_timeout act as an independent
per-attempt timeout instead of being indistinguishable from "nobody set it".
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import hangarllm
from hangarllm.constants import DEFAULT_REQUEST_TIMEOUT_SECONDS
from hangarllm.hangarllm_core_utils.request_timeout_resolver import (
    get_configured_request_timeout,
)


@pytest.fixture
def restore_request_timeout():
    original_value = hangarllm.request_timeout
    original_flag = hangarllm.request_timeout_explicitly_set
    try:
        yield
    finally:
        hangarllm.request_timeout = original_value
        hangarllm.request_timeout_explicitly_set = original_flag


def test_default_value_without_flag_is_unset(restore_request_timeout):
    hangarllm.request_timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
    hangarllm.request_timeout_explicitly_set = False
    assert get_configured_request_timeout() is None


def test_explicit_flag_returns_value(restore_request_timeout):
    hangarllm.request_timeout = 300
    hangarllm.request_timeout_explicitly_set = True
    assert get_configured_request_timeout() == 300.0


def test_explicit_flag_preserves_value_equal_to_default(restore_request_timeout):
    # The case the bare ``!= default`` heuristic gets wrong: a user who explicitly
    # configures the default value still means it explicitly.
    hangarllm.request_timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
    hangarllm.request_timeout_explicitly_set = True
    assert get_configured_request_timeout() == float(DEFAULT_REQUEST_TIMEOUT_SECONDS)


def test_non_default_runtime_value_treated_as_explicit(restore_request_timeout):
    # SDK users assigning hangarllm.request_timeout directly (no flag) must keep working.
    hangarllm.request_timeout = 300
    hangarllm.request_timeout_explicitly_set = False
    assert get_configured_request_timeout() == 300.0
