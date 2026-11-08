import asyncio
import importlib
import os

import pytest

import hangarllm
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
from hangarllm.types.files import (
    FILE_EXTENSIONS,
    FILE_MIME_TYPES,
    FileType,
    get_file_extension_for_file_type,
    get_file_extension_from_mime_type,
    get_file_mime_type_for_file_type,
    get_file_mime_type_from_extension,
    get_file_type_from_extension,
)
from hangarllm.utils import _invalidate_model_cost_lowercase_map
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome


class TestFileConsts:
    def test_all_file_types_have_extensions(self):
        for file_type in FileType:
            assert file_type in FILE_EXTENSIONS.keys()

    def test_all_file_types_have_mime_types(self):
        for file_type in FileType:
            assert file_type in FILE_MIME_TYPES.keys()

    def test_get_file_extension_from_mime_type(self):
        assert get_file_extension_from_mime_type("audio/aac") == "aac"
        assert get_file_extension_from_mime_type("application/pdf") == "pdf"
        with pytest.raises(ValueError, match="Unknown extension for mime type: application"):
            get_file_extension_from_mime_type("application/unknown")

    def test_get_file_type_from_extension(self):
        assert get_file_type_from_extension("aac") == FileType.AAC
        assert get_file_type_from_extension("pdf") == FileType.PDF
        with pytest.raises(ValueError, match="Unknown file type for extension: unknown"):
            get_file_type_from_extension("unknown")

    def test_get_file_extension_for_file_type(self):
        assert get_file_extension_for_file_type(FileType.AAC) == "aac"
        assert get_file_extension_for_file_type(FileType.PDF) == "pdf"

    def test_get_file_mime_type_for_file_type(self):
        assert get_file_mime_type_for_file_type(FileType.AAC) == "audio/aac"
        assert get_file_mime_type_for_file_type(FileType.PDF) == "application/pdf"

    def test_get_file_mime_type_from_extension(self):
        assert get_file_mime_type_from_extension("aac") == "audio/aac"
        assert get_file_mime_type_from_extension("pdf") == "application/pdf"

    def test_uppercase_extensions(self):
        # Test that uppercase extensions return the correct file type
        assert get_file_type_from_extension("AAC") == FileType.AAC
        assert get_file_type_from_extension("PDF") == FileType.PDF

        # Test that uppercase extensions return the correct MIME type
        assert get_file_mime_type_from_extension("AAC") == "audio/aac"
        assert get_file_mime_type_from_extension("PDF") == "application/pdf"


@pytest.fixture(autouse=True)
def _vcr_outcome_gate(request, vcr):
    install_live_call_probe(request, vcr)
    yield
    record_vcr_outcome(request, vcr)


@pytest.fixture(scope="function", autouse=True)
def isolate_hangarllm_state():
    """
    Per-function isolation fixture.

    Resets hangarllm globals to their true defaults before each test and
    restores them afterward, so tests don't leak side effects.
    Works safely under pytest-xdist parallel execution.
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
    for attr in ("pre_call_rules", "post_call_rules"):
        if hasattr(hangarllm, attr):
            val = getattr(hangarllm, attr)
            original_state[attr] = val.copy() if val else []
    for attr in _SCALAR_DEFAULTS:
        if hasattr(hangarllm, attr):
            original_state[attr] = getattr(hangarllm, attr)
    if hasattr(hangarllm, "in_memory_llm_clients_cache"):
        hangarllm.in_memory_llm_clients_cache.flush_cache()
    for attr in (
        "callbacks",
        "success_callback",
        "failure_callback",
        "_async_success_callback",
        "_async_failure_callback",
        "pre_call_rules",
        "post_call_rules",
    ):
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, [])
    for attr, default_val in _SCALAR_DEFAULTS.items():
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, default_val)
    yield
    asyncio.run(GLOBAL_LOGGING_WORKER.clear_queue())
    if hasattr(hangarllm, "in_memory_llm_clients_cache"):
        hangarllm.in_memory_llm_clients_cache.flush_cache()
    for attr, original_value in original_state.items():
        if hasattr(hangarllm, attr):
            setattr(hangarllm, attr, original_value)
    _invalidate_model_cost_lowercase_map()


_SCALAR_DEFAULTS = {
    "num_retries": getattr(hangarllm, "num_retries", None),
    "num_retries_per_request": getattr(hangarllm, "num_retries_per_request", None),
    "request_timeout": getattr(hangarllm, "request_timeout", None),
    "set_verbose": getattr(hangarllm, "set_verbose", False),
    "cache": getattr(hangarllm, "cache", None),
    "allowed_fails": getattr(hangarllm, "allowed_fails", 3),
    "default_fallbacks": getattr(hangarllm, "default_fallbacks", None),
    "enable_azure_ad_token_refresh": getattr(hangarllm, "enable_azure_ad_token_refresh", None),
    "tag_budget_config": getattr(hangarllm, "tag_budget_config", None),
    "model_cost": getattr(hangarllm, "model_cost", None),
    "token_counter": getattr(hangarllm, "token_counter", None),
    "disable_aiohttp_transport": getattr(hangarllm, "disable_aiohttp_transport", False),
    "force_ipv4": getattr(hangarllm, "force_ipv4", False),
    "drop_params": getattr(hangarllm, "drop_params", None),
    "modify_params": getattr(hangarllm, "modify_params", False),
    "api_base": getattr(hangarllm, "api_base", None),
    "api_key": getattr(hangarllm, "api_key", None),
}


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
        except Exception:
            pass
        if hasattr(hangarllm, "in_memory_llm_clients_cache"):
            hangarllm.in_memory_llm_clients_cache.flush_cache()
    yield
