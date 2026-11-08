import ast
import asyncio
import importlib
import os
from pathlib import Path

import pytest

import hangarllm
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
from hangarllm.utils import _invalidate_model_cost_lowercase_map
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome

LOCAL_TESTING_DIR = Path(__file__).parents[1] / "local_testing"


def _top_level_test_invocations(tree):
    invocations = []
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name and name.startswith("test_"):
            invocations.append((name, node.lineno))
    return invocations


def test_no_module_level_test_invocations():
    offenders = []
    for path in sorted(LOCAL_TESTING_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for name, lineno in _top_level_test_invocations(tree):
            offenders.append(f"{path.relative_to(LOCAL_TESTING_DIR)}:{lineno} calls {name}()")

    assert not offenders, (
        "Test functions are invoked at module scope, so they run during pytest "
        "collection (making network calls and erroring collection for every job "
        "that globs this directory). Remove these calls; pytest collects test "
        "functions automatically:\n" + "\n".join(offenders)
    )


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
