"""
Tests for Crusoe provider integration
"""

import asyncio
import importlib
import os
from unittest import mock

import pytest

import hangarllm
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome

CRUSOE_API_BASE = "https://api.inference.crusoecloud.com/v1"


def test_crusoe_json_registry():
    """Test CrusoeChatConfig is loaded from JSON provider registry"""
    from hangarllm.llms.openai_like.json_loader import JSONProviderRegistry

    assert JSONProviderRegistry.exists("crusoe")
    config = JSONProviderRegistry.get("crusoe")
    assert config is not None
    assert config.base_url == CRUSOE_API_BASE
    assert config.api_key_env == "CRUSOE_API_KEY"
    assert config.api_base_env == "CRUSOE_API_BASE"


def test_crusoe_get_openai_compatible_provider_info():
    """Test Crusoe provider info retrieval"""
    from hangarllm.llms.openai_like.dynamic_config import create_config_class
    from hangarllm.llms.openai_like.json_loader import JSONProviderRegistry

    config = create_config_class(JSONProviderRegistry.get("crusoe"))()

    # Test with default values (no env vars set)
    with mock.patch.dict(os.environ, {}, clear=True):
        api_base, api_key = config.get_openai_compatible_provider_info(None, None)
        assert api_base == CRUSOE_API_BASE
        assert api_key is None

    # Test with environment variables
    with mock.patch.dict(
        os.environ,
        {
            "CRUSOE_API_KEY": "test-key",
            "CRUSOE_API_BASE": "https://custom.crusoecloud.com/v1",
        },
    ):
        api_base, api_key = config.get_openai_compatible_provider_info(None, None)
        assert api_base == "https://custom.crusoecloud.com/v1"
        assert api_key == "test-key"

    # Test with explicit parameters (should override env vars)
    with mock.patch.dict(
        os.environ,
        {
            "CRUSOE_API_KEY": "env-key",
            "CRUSOE_API_BASE": "https://env.crusoecloud.com/v1",
        },
    ):
        api_base, api_key = config.get_openai_compatible_provider_info("https://param.crusoecloud.com/v1", "param-key")
        assert api_base == "https://param.crusoecloud.com/v1"
        assert api_key == "param-key"


def test_get_llm_provider_crusoe():
    """Test that get_llm_provider correctly identifies Crusoe"""
    from hangarllm.hangarllm_core_utils.get_llm_provider_logic import get_llm_provider

    # Test with crusoe/model-name format
    model, provider, api_key, api_base = get_llm_provider("crusoe/meta-llama/Llama-3.3-70B-Instruct")
    assert model == "meta-llama/Llama-3.3-70B-Instruct"
    assert provider == "crusoe"


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
