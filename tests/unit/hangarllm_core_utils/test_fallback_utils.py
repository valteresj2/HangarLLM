"""Tests for hangarllm.hangarllm_core_utils.fallback_utils."""

import json
import pathlib
from typing import Final

import httpx
import pytest
import respx

import hangarllm
from hangarllm.hangarllm_core_utils import hangarllm_logging
from hangarllm.hangarllm_core_utils.core_helpers import process_response_headers
from hangarllm.hangarllm_core_utils.fallback_utils import (
    async_completion_with_fallbacks,
)
from hangarllm.main import acompletion as python_acompletion
from hangarllm.main import completion as python_completion
from hangarllm.vector_stores.vector_store_registry import HangarLLM_ManagedVectorStore, VectorStoreRegistry


@pytest.mark.asyncio
async def test_fallback_dict_not_mutated(monkeypatch):
    fallback_dict = {"model": "fallback-model", "temperature": 0.2}
    original_fallback_dict = dict(fallback_dict)

    attempted_models: list[str] = []

    async def _fake_acompletion(*, model: str, **kwargs):
        attempted_models.append(model)
        if model == "primary-model":
            raise Exception("primary failed")
        return {"model": model, "temperature": kwargs.get("temperature")}

    monkeypatch.setattr(hangarllm, "acompletion", _fake_acompletion)

    # Call 1: primary fails, fallback dict succeeds
    response_1 = await async_completion_with_fallbacks(
        model="primary-model",
        kwargs={"fallbacks": [fallback_dict]},
    )
    assert response_1["model"] == "fallback-model"
    assert fallback_dict == original_fallback_dict

    # Call 2: re-use the same dict object; it should still work and remain unchanged
    response_2 = await async_completion_with_fallbacks(
        model="primary-model",
        kwargs={"fallbacks": [fallback_dict]},
    )
    assert response_2["model"] == "fallback-model"
    assert fallback_dict == original_fallback_dict

    assert attempted_models == [
        "primary-model",
        "fallback-model",
        "primary-model",
        "fallback-model",
    ]


@pytest.mark.asyncio
async def test_async_completion_with_fallbacks_sets_attempted_fallbacks_header():
    """
    When a fallback succeeds, the response must carry the
    `x-hangarllm-attempted-fallbacks` header so the proxy and other callers can
    detect that a fallback occurred. Without it,
    `_override_openai_response_model` stamps the requested model back over the
    fallback model used. See issue #28241.
    """
    response = await async_completion_with_fallbacks(
        model="openai/primary-llm",
        messages=[{"role": "user", "content": "hi"}],
        api_key="fake-key",
        mock_response=Exception("forced failure"),
        kwargs={
            "fallbacks": [
                {
                    "model": "openai/backup-llm",
                    "api_key": "fake-key",
                    "mock_response": "backup-resp",
                }
            ]
        },
    )

    hidden_params = getattr(response, "_hidden_params", None)
    assert isinstance(hidden_params, dict)
    headers = hidden_params.get("additional_headers") or {}
    assert headers.get("x-hangarllm-attempted-fallbacks") == 1


@pytest.mark.asyncio
async def test_async_completion_with_fallbacks_header_is_zero_when_primary_succeeds():
    """
    When the primary model succeeds on the first attempt, the header should be
    `0` (no fallback was used). This mirrors the existing router-level
    semantics in `async_function_with_fallbacks`.
    """
    response = await async_completion_with_fallbacks(
        model="openai/primary-llm",
        messages=[{"role": "user", "content": "hi"}],
        api_key="fake-key",
        mock_response="primary-resp",
        kwargs={
            "fallbacks": [
                {
                    "model": "openai/backup-llm",
                    "api_key": "fake-key",
                    "mock_response": "backup-resp",
                }
            ]
        },
    )

    hidden_params = getattr(response, "_hidden_params", None)
    assert isinstance(hidden_params, dict)
    headers = hidden_params.get("additional_headers") or {}
    assert headers.get("x-hangarllm-attempted-fallbacks") == 0
    assert response.choices[0].message.content == "primary-resp"


def test_process_response_headers_preserves_x_hangarllm_headers_when_internal():
    """
    `process_response_headers` must not add the `llm_provider-` prefix to
    HangarLLM's own internal headers (anything starting with `x-hangarllm-`) when
    the caller has marked the input as HangarLLM-owned. These are markers set by
    HangarLLM (e.g. fallback / retry headers); the proxy and other callers look
    up the bare key.
    """
    result = process_response_headers(
        {
            "x-hangarllm-attempted-fallbacks": 1,
            "x-hangarllm-model-group": "gpt-4",
            "x-stainless-arch": "arm64",
        },
        preserve_hangarllm_internal_headers=True,
    )
    assert result["x-hangarllm-attempted-fallbacks"] == 1
    assert result["x-hangarllm-model-group"] == "gpt-4"
    assert result["llm_provider-x-stainless-arch"] == "arm64"


def test_process_response_headers_prefixes_x_hangarllm_from_raw_provider():
    """
    On raw upstream-provider headers (default `preserve_hangarllm_internal_headers=False`),
    a header whose name starts with `x-hangarllm-` MUST still get the
    `llm_provider-` prefix. Otherwise a malicious provider could return
    `x-hangarllm-attempted-fallbacks` and spoof a HangarLLM-internal marker,
    bypassing the proxy model-override guard.
    """
    result = process_response_headers(
        {
            "x-hangarllm-attempted-fallbacks": 99,
            "x-stainless-arch": "arm64",
        }
    )
    assert "x-hangarllm-attempted-fallbacks" not in result
    assert result["llm_provider-x-hangarllm-attempted-fallbacks"] == 99
    assert result["llm_provider-x-stainless-arch"] == "arm64"


def test_process_response_headers_ignores_preserve_flag_for_httpx_headers():
    """
    Some providers store raw httpx.Headers directly in _hidden_params["additional_headers"]
    without a prior normalization pass. If preserve_hangarllm_internal_headers=True were
    honored for httpx.Headers inputs, a provider returning x-hangarllm-attempted-fallbacks
    could spoof it as a bare HangarLLM-internal marker and make the proxy skip
    stamping the correct response model. The flag must be ignored for httpx.Headers.
    """
    raw = httpx.Headers(
        {
            "x-hangarllm-attempted-fallbacks": "1",
            "content-type": "application/json",
        }
    )
    result = process_response_headers(raw, preserve_hangarllm_internal_headers=True)
    assert "x-hangarllm-attempted-fallbacks" not in result
    assert result["llm_provider-x-hangarllm-attempted-fallbacks"] == "1"


@pytest.mark.asyncio
async def test_acompletion_fallbacks_bad_models(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=(
            httpx.Response(
                404,
                json={
                    "error": {
                        "message": "model unavailable",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "model_not_found",
                    }
                },
            ),
            httpx.Response(
                404,
                json={
                    "error": {
                        "message": "fallback unavailable",
                        "type": "authentication_error",
                        "param": None,
                        "code": "model_not_found",
                    }
                },
            ),
        )
    )

    with pytest.raises(Exception, match="All fallback attempts failed"):
        await python_acompletion(
            model="openai/first",
            messages=[{"role": "user", "content": "hello"}],
            api_key="test-key",
            fallbacks=["openai/second"],
        )

    assert len(route.calls) == 2


@pytest.mark.asyncio
async def test_acompletion_fallbacks_basic(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=(
            httpx.Response(
                404,
                json={
                    "error": {
                        "message": "model unavailable",
                        "type": "authentication_error",
                        "param": None,
                        "code": "model_not_found",
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": "chatcmpl-fallback",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "second",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "fallback answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            ),
        )
    )

    response: Final = await python_acompletion(
        model="openai/first",
        messages=[{"role": "user", "content": "hello"}],
        api_key="test-key",
        fallbacks=["openai/second"],
    )

    assert response.choices[0].message.content == "fallback answer"
    assert tuple(json.loads(call.request.content)["model"] for call in route.calls) == ("first", "second")


@pytest.mark.asyncio
async def test_acompletion_fallbacks_empty_list(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            404,
            json={
                "error": {
                    "message": "model unavailable",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "model_not_found",
                }
            },
        )
    )

    with pytest.raises(hangarllm.NotFoundError, match="model unavailable"):
        await python_acompletion(
            model="openai/first",
            messages=[{"role": "user", "content": "hello"}],
            api_key="test-key",
            fallbacks=[],
        )

    assert len(route.calls) == 1


@pytest.mark.asyncio
async def test_acompletion_fallbacks_none_response(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=(
            httpx.Response(
                500,
                json={
                    "error": {
                        "message": "temporary failure",
                        "type": "server_error",
                        "param": None,
                        "code": "server_error",
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": "chatcmpl-fallback",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "second",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "recovered answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            ),
        )
    )

    response: Final = await python_acompletion(
        model="openai/first",
        messages=[{"role": "user", "content": "hello"}],
        api_key="test-key",
        fallbacks=["openai/second"],
    )

    assert response.choices[0].message.content == "recovered answer"
    assert len(route.calls) == 2


@pytest.mark.asyncio
async def test_acompletion_fallbacks_with_dict_config(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=(
            httpx.Response(
                401,
                json={
                    "error": {
                        "message": "invalid key",
                        "type": "authentication_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": "chatcmpl-fallback",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "first",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "authenticated answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            ),
        )
    )

    response: Final = await python_acompletion(
        model="openai/first",
        messages=[{"role": "user", "content": "hello"}],
        api_key="invalid-key",
        fallbacks=[{"api_key": "fallback-key"}],
    )

    assert response.choices[0].message.content == "authenticated answer"
    assert tuple(call.request.headers["authorization"] for call in route.calls) == (
        "Bearer invalid-key",
        "Bearer fallback-key",
    )


def test_completion_fallbacks_sync(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=(
            httpx.Response(
                404,
                json={
                    "error": {
                        "message": "model unavailable",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "model_not_found",
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "id": "chatcmpl-fallback",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "second",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "sync fallback answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            ),
        )
    )

    response: Final = python_completion(
        model="openai/first",
        messages=[{"role": "user", "content": "hello"}],
        api_key="test-key",
        fallbacks=["openai/second"],
    )

    assert response.choices[0].message.content == "sync fallback answer"
    assert tuple(json.loads(call.request.content)["model"] for call in route.calls) == ("first", "second")


CACHE_POINTS: Final = ({"location": "message", "role": "system"},)
CACHED_MESSAGES: Final = (
    {"role": "system", "content": "You are a careful assistant."},
    {"role": "user", "content": "hello"},
)
OPENAI_ANSWER: Final = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-6.1-sol",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}
ANTHROPIC_ANSWER: Final = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-haiku-4-5",
    "content": [{"type": "text", "text": "ok"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 1, "output_tokens": 1},
}


def _cached_request(**kwargs: object) -> dict[str, object]:
    return {
        "messages": [dict(message) for message in CACHED_MESSAGES],
        "cache_control_injection_points": [dict(point) for point in CACHE_POINTS],
        **kwargs,
    }


@pytest.mark.asyncio
async def test_acompletion_fallback_sends_the_fallback_model_the_request_a_direct_call_sends(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    openai_route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"message": "invalid key", "type": "authentication_error", "param": None, "code": None}},
        )
    )
    anthropic_route: Final = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_ANSWER)
    )

    await python_acompletion(**_cached_request(model="anthropic/claude-haiku-4-5", api_key="anthropic-key"))
    await python_acompletion(
        **_cached_request(
            model="openai/gpt-6.1-sol",
            api_key="openai-key",
            fallbacks=[{"model": "anthropic/claude-haiku-4-5", "api_key": "anthropic-key"}],
        )
    )

    assert "prompt_cache_options" in json.loads(openai_route.calls[0].request.content)
    direct_body, fallback_body = (json.loads(call.request.content) for call in anthropic_route.calls)
    assert fallback_body == direct_body


@pytest.mark.parametrize("is_async", [True, False])
@pytest.mark.asyncio
async def test_cache_dialect_follows_base_url_over_an_api_base_the_call_does_not_use(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch, is_async: bool
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_ANSWER)
    )

    async def send(**kwargs: object) -> None:
        request: Final = _cached_request(
            model="openai/gpt-6.1-sol", api_key="openai-key", base_url="https://api.openai.com/v1", **kwargs
        )
        if is_async:
            await python_acompletion(**request)
        else:
            python_completion(**request)

    await send()
    await send(api_base="https://unused-gateway.example.com/v1")

    base_url_only, with_unused_api_base = (json.loads(call.request.content) for call in route.calls)
    assert with_unused_api_base == base_url_only


@pytest.mark.asyncio
async def test_acompletion_fallback_sends_the_context_a_vector_store_tool_retrieves(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    monkeypatch.setattr(
        hangarllm,
        "vector_store_registry",
        VectorStoreRegistry(
            vector_stores=[
                HangarLLM_ManagedVectorStore(
                    vector_store_id="vs_docs", custom_llm_provider="openai", hangarllm_params={"api_key": "openai-key"}
                )
            ]
        ),
    )
    search_route: Final = respx_mock.post("https://api.openai.com/v1/vector_stores/vs_docs/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "vector_store.search_results.page",
                "search_query": "what is hangarllm?",
                "data": [{"score": 1.0, "content": [{"type": "text", "text": "hangarllm is an LLM gateway"}]}],
            },
        )
    )
    openai_route: Final = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"message": "invalid key", "type": "authentication_error", "param": None, "code": None}},
        )
    )
    anthropic_route: Final = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_ANSWER)
    )

    async def send(**kwargs: object) -> None:
        await python_acompletion(
            messages=[{"role": "user", "content": "what is hangarllm?"}],
            tools=[{"type": "file_search", "vector_store_ids": ["vs_docs"]}],
            **kwargs,
        )

    await send(model="anthropic/claude-haiku-4-5", api_key="anthropic-key")
    await send(
        model="openai/gpt-6.1-sol",
        api_key="openai-key",
        fallbacks=[{"model": "anthropic/claude-haiku-4-5", "api_key": "anthropic-key"}],
    )

    direct_body, fallback_body = (json.loads(call.request.content) for call in anthropic_route.calls)
    assert "hangarllm is an LLM gateway" in json.dumps(direct_body)
    assert fallback_body == direct_body
    assert search_route.call_count <= openai_route.call_count + anthropic_route.call_count


@pytest.mark.asyncio
async def test_acompletion_fallback_sends_the_prompt_the_primary_model_prefix_template_renders(
    respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _ = (tmp_path / "brief.prompt").write_text(
        "---\ninput:\n  schema:\n    question: string\n---\nSystem: Answer in one word.\n\nUser: {{question}}\n"
    )
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    monkeypatch.setattr(hangarllm, "global_prompt_directory", str(tmp_path))
    monkeypatch.setattr(hangarllm_logging, "_in_memory_loggers", [])
    _ = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"message": "invalid key", "type": "authentication_error", "param": None, "code": None}},
        )
    )
    anthropic_route: Final = respx_mock.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_ANSWER)
    )

    async def send(**kwargs: object) -> None:
        await python_acompletion(
            prompt_id="brief",
            prompt_variables={"question": "What color is the sky?"},
            messages=[{"role": "user", "content": "placeholder"}],
            **kwargs,
        )

    await send(model="dotprompt/anthropic/claude-haiku-4-5", api_key="anthropic-key")
    await send(
        model="dotprompt/openai/gpt-6.1-sol",
        api_key="openai-key",
        fallbacks=[{"model": "anthropic/claude-haiku-4-5", "api_key": "anthropic-key"}],
    )

    direct_body, fallback_body = (json.loads(call.request.content) for call in anthropic_route.calls)
    assert "What color is the sky?" in json.dumps(direct_body)
    assert fallback_body == direct_body
