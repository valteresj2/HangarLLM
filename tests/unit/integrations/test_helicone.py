import asyncio, copy, importlib, hangarllm, logging, os, pytest, sys, time
import types


from hangarllm.integrations.helicone import HeliconeLogger
from collections.abc import Iterator
from pathlib import Path
from typing import Final
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
from hangarllm.utils import _invalidate_model_cost_lowercase_map
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome
from unittest.mock import MagicMock


def _claude_mapping(messages, response_obj):
    logger = HeliconeLogger.__new__(HeliconeLogger)
    return logger.claude_mapping(model="gpt-5.6", messages=messages, response_obj=response_obj)


@pytest.fixture()
def anthropic_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Stub the anthropic module unconditionally: the SDK may be absent (it lives in the
    proxy-runtime extra), and the tests/unit/llms/anthropic test package can
    shadow it on sys.path, so an import probe proves nothing about the real SDK.
    """
    stub = types.ModuleType("anthropic")
    stub.HUMAN_PROMPT = "\n\nHuman:"
    stub.AI_PROMPT = "\n\nAssistant:"
    monkeypatch.setitem(sys.modules, "anthropic", stub)


@pytest.mark.usefixtures("anthropic_prompts")
def test_claude_mapping_serializes_custom_tool_calls():
    response_obj = {
        "id": "chatcmpl-1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_c",
                            "type": "custom",
                            "custom": {"name": "ApplyPatch", "input": "*** Begin Patch"},
                        },
                        {
                            "id": "call_f",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
                        },
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    mapped = _claude_mapping([{"role": "user", "content": "hi"}], response_obj)
    tool_use_blocks = [b for b in mapped["content"] if b["type"] == "tool_use"]
    assert {"type": "tool_use", "id": "call_c", "name": "ApplyPatch", "input": "*** Begin Patch"} in tool_use_blocks
    assert {"type": "tool_use", "id": "call_f", "name": "read_file", "input": '{"path": "a.py"}'} in tool_use_blocks


@pytest.mark.usefixtures("anthropic_prompts")
def test_claude_mapping_puts_server_tool_calls_first_as_tool_use_blocks():
    response_obj: Final = {
        "id": "chatcmpl-1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_f",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
                        },
                    ],
                    "provider_specific_fields": {
                        "server_tool_calls": [
                            {
                                "id": "srvtoolu_01",
                                "type": "function",
                                "function": {"name": "web_search", "arguments": '{"query": "persimmon"}'},
                            }
                        ]
                    },
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }
    mapped: Final = _claude_mapping([{"role": "user", "content": "hi"}], response_obj)
    assert mapped["content"] == [
        {"type": "tool_use", "id": "srvtoolu_01", "name": "web_search", "input": '{"query": "persimmon"}'},
        {"type": "tool_use", "id": "call_f", "name": "read_file", "input": '{"path": "a.py"}'},
    ]


@pytest.fixture()
def _vcr_outcome_gate(request, vcr):
    install_live_call_probe(request, vcr)
    yield
    record_vcr_outcome(request, vcr)

@pytest.fixture(scope="function")
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

@pytest.fixture(scope="module")
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

@pytest.fixture
def helicone_global_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    root_logger: Final = logging.getLogger()
    original_handlers: Final = tuple(root_logger.handlers)
    original_level: Final = root_logger.level
    try:
        root_logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
        monkeypatch.setattr(hangarllm, "num_retries", 3)
        monkeypatch.setattr(hangarllm, "success_callback", ["helicone"])
        monkeypatch.setenv("HELICONE_DEBUG", "True")
        monkeypatch.setenv("HANGARLLM_LOG", "DEBUG")
        yield tmp_path
    finally:
        added_handlers: Final = tuple(
            handler for handler in root_logger.handlers if handler not in original_handlers
        )
        root_logger.handlers = list(original_handlers)
        root_logger.setLevel(original_level)
        for handler in added_handlers:
            handler.close()

def pre_helicone_setup(log_path: Path) -> None:
    """
    Set up the logging for the 'pre_helicone_setup' function.
    """
    import logging

    logging.basicConfig(filename=log_path, level=logging.DEBUG)
    logger = logging.getLogger()

    file_handler = logging.FileHandler(log_path, mode="w")
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown", "helicone_global_state")
def test_helicone_logging_async(helicone_global_state: Path):
    try:
        pre_helicone_setup(helicone_global_state / "helicone.log")
        hangarllm.success_callback = []
        start_time_empty_callback = asyncio.run(make_async_calls())
        print("done with no callback test")

        print("starting helicone test")
        hangarllm.success_callback = ["helicone"]
        start_time_helicone = asyncio.run(make_async_calls())
        print("done with helicone test")

        print(f"Time taken with success_callback='helicone': {start_time_helicone}")
        print(f"Time taken with empty success_callback: {start_time_empty_callback}")

        assert abs(start_time_helicone - start_time_empty_callback) < 1

    except hangarllm.Timeout as e:
        pass
    except Exception as e:
        pytest.fail(f"An exception occurred - {e}")

async def make_async_calls(metadata=None, **completion_kwargs):
    tasks = []
    for _ in range(5):
        tasks.append(create_async_task())

    start_time = asyncio.get_event_loop().time()

    responses = await asyncio.gather(*tasks)

    for idx, response in enumerate(responses):
        print(f"Response from Task {idx + 1}: {response}")

    total_time = asyncio.get_event_loop().time() - start_time

    return total_time

def create_async_task(**completion_kwargs):
    completion_args = {
        "model": "azure/gpt-4.1-mini",
        "api_version": "2024-02-01",
        "messages": [{"role": "user", "content": "This is a test"}],
        "max_tokens": 5,
        "temperature": 0.7,
        "timeout": 5,
        "user": "helicone_latency_test_user",
        "mock_response": "It's simple to use and easy to get started",
    }
    completion_args.update(completion_kwargs)
    return asyncio.create_task(hangarllm.acompletion(**completion_args))

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown", "helicone_global_state")
@pytest.mark.asyncio
@pytest.mark.skipif(
    condition=not os.environ.get("OPENAI_API_KEY", False),
    reason="Authentication missing for openai",
)
async def test_helicone_logging_metadata():
    from hangarllm._uuid import uuid

    hangarllm.success_callback = ["helicone"]

    request_id = str(uuid.uuid4())
    trace_common_metadata = {"Helicone-Property-Request-Id": request_id}

    metadata = copy.deepcopy(trace_common_metadata)
    metadata["Helicone-Property-Conversation"] = "support_issue"
    metadata["Helicone-Auth"] = os.getenv("HELICONE_API_KEY")
    response = await create_async_task(
        model="gpt-3.5-turbo",
        mock_response="Hey! how's it going?",
        messages=[
            {
                "role": "user",
                "content": f"{request_id}",
            }
        ],
        max_tokens=100,
        temperature=0.2,
        metadata=copy.deepcopy(metadata),
    )
    print(response)

    time.sleep(3)

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown", "helicone_global_state")
def test_helicone_removes_otel_span_from_metadata():
    """
    Test that HeliconeLogger removes hangarllm_parent_otel_span from metadata
    to prevent JSON serialization errors.
    """
    from hangarllm.integrations.helicone import HeliconeLogger

    # Create a mock span object (similar to what OpenTelemetry would create)
    mock_span = MagicMock()
    mock_span.__class__.__name__ = "_Span"

    # Create metadata with the problematic span object
    metadata = {
        "user_id": "test_user",
        "request_id": "test_request_123",
        "hangarllm_parent_otel_span": mock_span,  # This would cause JSON serialization error
        "other_metadata": "some_value",
    }

    # Create HeliconeLogger instance
    logger = HeliconeLogger()

    # Test the add_metadata_from_header method
    hangarllm_params = {"proxy_server_request": {"headers": {}}}
    result_metadata = logger.add_metadata_from_header(hangarllm_params, metadata)

    # Verify that hangarllm_parent_otel_span was removed
    assert "hangarllm_parent_otel_span" not in result_metadata
    assert "user_id" in result_metadata
    assert "request_id" in result_metadata
    assert "other_metadata" in result_metadata
    assert result_metadata["user_id"] == "test_user"
    assert result_metadata["request_id"] == "test_request_123"
    assert result_metadata["other_metadata"] == "some_value"

    print("✅ Test passed: hangarllm_parent_otel_span was successfully removed from metadata")
