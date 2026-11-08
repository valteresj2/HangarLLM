from collections.abc import Iterator
from pathlib import Path
from typing import Final

import respx

import asyncio, httpx, importlib, os
import pytest

import hangarllm
from hangarllm import CustomLLM
from hangarllm.hangarllm_core_utils import get_llm_provider_logic
from hangarllm.hangarllm_core_utils.get_llm_provider_logic import (
    get_llm_provider,
    resolve_model_and_provider_for_metadata,
    get_provider_affinity_header,
    inferred_provider,
    is_registered_custom_provider,
)
from hangarllm.llms.custom_httpx.http_handler import HTTPHandler
from hangarllm.hangarllm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
from hangarllm.hangarllm_core_utils.model_latest_aliases import get_model_latest_aliases
from hangarllm.types.router import HangarLLM_Params
from hangarllm.utils import _invalidate_model_cost_lowercase_map
from tests._vcr_conftest_common import install_live_call_probe, record_vcr_outcome
from unittest.mock import patch

CUSTOM_PROVIDER: Final = "test-onprem-llm"


@pytest.mark.parametrize(
    ("model", "provider"),
    (("openai/gpt-luna-latest", None), ("gpt-luna-latest", "openai")),
)
def test_latest_alias_resolves_to_the_bundled_target(model: str, provider: str | None) -> None:
    target: Final = get_model_latest_aliases()["openai"]["gpt-luna-latest"]
    resolved, resolved_provider, _, api_base = get_llm_provider(
        model, custom_llm_provider=provider, api_base="https://api.openai.com/v1"
    )
    assert (resolved, resolved_provider, api_base) == (target, "openai", "https://api.openai.com/v1")


@pytest.mark.parametrize(
    "model",
    ("gemini/gemini-pro-latest", "gemini/gemini-flash-latest", "dashscope/qwen-plus-latest", "mistral/mistral-large-latest"),
)
def test_provider_native_latest_alias_passes_through(model: str) -> None:
    provider, name = model.split("/", 1)
    assert get_llm_provider(model)[:2] == (name, provider)


def test_latest_alias_completion_reports_and_prices_the_target() -> None:
    target: Final = get_model_latest_aliases()["anthropic"]["claude-opus-latest"]
    response: Final = hangarllm.completion(
        model="anthropic/claude-opus-latest", messages=[{"role": "user", "content": "hi"}], mock_response="hi"
    )
    assert response.model == target
    cost: Final = hangarllm.completion_cost(completion_response=response)
    assert cost is not None and cost > 0
    assert cost == hangarllm.completion_cost(completion_response=response, model=target, custom_llm_provider="anthropic")


@pytest.fixture
def registered_custom_provider(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(hangarllm, "custom_provider_map", [{"provider": CUSTOM_PROVIDER, "custom_handler": CustomLLM()}])
    monkeypatch.setattr(hangarllm, "provider_list", list(hangarllm.provider_list))
    monkeypatch.setattr(hangarllm, "_custom_providers", list(hangarllm._custom_providers))
    return CUSTOM_PROVIDER


def test_get_llm_provider_resolves_custom_provider_map_prefix_before_first_completion(
    registered_custom_provider: str,
) -> None:
    assert registered_custom_provider not in hangarllm.provider_list

    model, provider, dynamic_api_key, api_base = get_llm_provider(model=f"{registered_custom_provider}/my-model")

    assert (model, provider, dynamic_api_key, api_base) == ("my-model", registered_custom_provider, None, None)


def test_get_llm_provider_strips_prefix_when_custom_provider_passed_explicitly(
    registered_custom_provider: str,
) -> None:
    model, provider, _, api_base = get_llm_provider(
        model="my-model",
        custom_llm_provider=registered_custom_provider,
        api_base="http://onprem.internal:8080",
    )

    assert (model, provider, api_base) == ("my-model", registered_custom_provider, "http://onprem.internal:8080")


def test_get_llm_provider_still_rejects_unregistered_prefix(registered_custom_provider: str) -> None:
    with pytest.raises(hangarllm.BadRequestError, match="LLM Provider NOT provided"):
        get_llm_provider(model="not-registered-llm/my-model")


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [(CUSTOM_PROVIDER, True), ("not-registered-llm", False), (None, False), ("", False)],
)
def test_is_registered_custom_provider(registered_custom_provider: str, candidate: str | None, expected: bool) -> None:
    assert is_registered_custom_provider(candidate) is expected


def test_get_llm_provider_leaves_fal_ai_api_base_unset_for_global_fallback() -> None:
    _, provider, _, api_base = get_llm_provider(model="fal_ai/fal-ai/flux/schnell")
    assert provider == "fal_ai"
    assert api_base is None

    _, _, _, explicit = get_llm_provider(model="fal_ai/fal-ai/flux/schnell", api_base="http://edge.local/fal")
    assert explicit == "http://edge.local/fal"


def test_image_generation_fal_ai_egresses_to_global_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hangarllm, "api_base", "http://gateway.local/fal")
    monkeypatch.setenv("FAL_AI_API_KEY", "test")
    seen: Final[list[httpx.URL]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"images": [{"url": "https://fal.media/a.png"}]})

    client: Final = HTTPHandler(client=httpx.Client(transport=httpx.MockTransport(handler)))
    hangarllm.image_generation(model="fal_ai/fal-ai/flux/schnell", prompt="a red kite", client=client)
    assert str(seen[0]).startswith("http://gateway.local/fal")


def test_inferred_provider_adopts_a_declared_authenticating_provider_without_resolving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _oauth_tripwire(model: str, *args: object, **kwargs: object) -> None:
        raise AssertionError(f"get_llm_provider would run the OAuth device flow for {model}")

    monkeypatch.setattr(get_llm_provider_logic, "get_llm_provider", _oauth_tripwire)

    assert inferred_provider("github_copilot/gpt-5.5") == "github_copilot"


def test_inferred_provider_matches_the_resolver_for_a_bare_model_name() -> None:
    assert inferred_provider("claude-sonnet-4-6") == get_llm_provider(model="claude-sonnet-4-6")[1]
    assert inferred_provider("gpt-5.5-pro") == get_llm_provider(model="gpt-5.5-pro")[1]


@pytest.mark.parametrize("model", ["some-unknown-model-xyz", "", None], ids=["unknown", "empty", "missing"])
def test_inferred_provider_is_none_when_nothing_resolves(model: str | None) -> None:
    assert inferred_provider(model) is None


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

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider():
    _, response, _, _ = hangarllm.get_llm_provider(model="anthropic.claude-v2:1")

    assert response == "bedrock"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_fireworks():  # tests finetuned fireworks models - upstream issue 4923
    model, custom_llm_provider, _, _ = hangarllm.get_llm_provider(model="fireworks_ai/accounts/my-test-1234")

    assert custom_llm_provider == "fireworks_ai"
    assert model == "accounts/my-test-1234"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_catch_all():
    _, response, _, _ = hangarllm.get_llm_provider(model="*")
    assert response == "openai"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_gpt_instruct():
    _, response, _, _ = hangarllm.get_llm_provider(model="gpt-3.5-turbo-instruct-0914")

    assert response == "text-completion-openai"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_mistral_custom_api_base():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="mistral/mistral-large-fr",
        api_base="https://mistral-large-fr-ishaan.francecentral.inference.ai.azure.com/v1",
    )
    assert custom_llm_provider == "mistral"
    assert model == "mistral-large-fr"
    assert api_base == "https://mistral-large-fr-ishaan.francecentral.inference.ai.azure.com/v1"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_deepseek_custom_api_base():
    os.environ["DEEPSEEK_API_BASE"] = "MY-FAKE-BASE"
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="deepseek/deep-chat",
    )
    assert custom_llm_provider == "deepseek"
    assert model == "deep-chat"
    assert api_base == "MY-FAKE-BASE"

    os.environ.pop("DEEPSEEK_API_BASE")

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_vertex_ai_image_models(monkeypatch):
    monkeypatch.setattr(hangarllm, "vertex_ai_image_models", set())
    monkeypatch.setattr(hangarllm, "models_by_provider", dict(hangarllm.models_by_provider))
    hangarllm.add_known_models(
        model_cost_map={
            "vertex_ai/imagegeneration@006": {
                "hangarllm_provider": "vertex_ai-image-models",
                "mode": "image_generation",
            }
        }
    )
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="imagegeneration@006", custom_llm_provider=None
    )
    assert custom_llm_provider == "vertex_ai"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_ai21_chat():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="jamba-1.5-large",
    )
    assert custom_llm_provider == "ai21_chat"
    assert model == "jamba-1.5-large"
    assert api_base == "https://api.ai21.com/studio/v1"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_ai21_chat_test2():
    """
    if user prefix with ai21/ but calls jamba-1.5-large then it should be ai21_chat provider
    """
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="ai21/jamba-1.5-large",
    )

    print("model=", model)
    print("custom_llm_provider=", custom_llm_provider)
    print("api_base=", api_base)
    assert custom_llm_provider == "ai21_chat"
    assert model == "jamba-1.5-large"
    assert api_base == "https://api.ai21.com/studio/v1"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_cohere_chat_test2():
    """
    if user prefix with cohere/ but calls command-r-plus-08-2024 then it should be cohere_chat provider
    """
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="cohere/command-r-plus-08-2024",
    )

    print("model=", model)
    print("custom_llm_provider=", custom_llm_provider)
    print("api_base=", api_base)
    assert custom_llm_provider == "cohere_chat"
    assert model == "command-r-plus-08-2024"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_azure_o1():

    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="azure/o1-mini",
    )
    assert custom_llm_provider == "azure"
    assert model == "o1-mini"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_hosted_vllm_default_api_key():
    from hangarllm.hangarllm_core_utils.get_llm_provider_logic import (
        _get_openai_compatible_provider_info,
    )

    _, _, dynamic_api_key, _ = _get_openai_compatible_provider_info(
        model="hosted_vllm/llama-3.1-70b-instruct",
        api_base=None,
        api_key=None,
        dynamic_api_key=None,
    )
    assert dynamic_api_key == "fake-api-key"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_jina_ai():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="jina_ai/jina-embeddings-v3",
    )
    assert custom_llm_provider == "jina_ai"
    assert api_base == "https://api.jina.ai/v1"
    assert model == "jina-embeddings-v3"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_hosted_vllm():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="hosted_vllm/llama-3.1-70b-instruct",
    )
    assert custom_llm_provider == "hosted_vllm"
    assert model == "llama-3.1-70b-instruct"
    assert dynamic_api_key == "fake-api-key"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_llamafile():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="llamafile/mistralai/mistral-7b-instruct-v0.2",
    )
    assert custom_llm_provider == "llamafile"
    assert model == "mistralai/mistral-7b-instruct-v0.2"
    assert dynamic_api_key == "fake-api-key"
    assert api_base == "http://127.0.0.1:8080/v1"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_watson_text():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="watsonx_text/watson-text-to-speech",
    )
    assert custom_llm_provider == "watsonx_text"
    assert model == "watson-text-to-speech"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_azure_global_standard_get_llm_provider():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="azure_ai/gpt-4o-global-standard",
        api_base="https://my-deployment-francecentral.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview",
        api_key="fake-api-key",
    )
    assert custom_llm_provider == "azure_ai"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_nova_bedrock_converse():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="amazon.nova-micro-v1:0",
    )
    assert custom_llm_provider == "bedrock"
    assert model == "amazon.nova-micro-v1:0"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_bedrock_invoke_anthropic():
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(
        model="bedrock/invoke/anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    assert custom_llm_provider == "bedrock"
    assert model == "invoke/anthropic.claude-haiku-4-5-20251001-v1:0"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
@pytest.mark.parametrize("model", ["xai/grok-2-vision-latest", "grok-2-vision-latest"])
def test_xai_api_base(model):
    args = {
        "model": model,
        "custom_llm_provider": "xai",
        "api_base": None,
        "api_key": "xai-my-specialkey",
        "hangarllm_params": None,
    }
    model, custom_llm_provider, dynamic_api_key, api_base = hangarllm.get_llm_provider(**args)
    assert custom_llm_provider == "xai"
    assert model == "grok-2-vision-latest"
    assert api_base == "https://api.x.ai/v1"
    assert dynamic_api_key == "xai-my-specialkey"

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_hangarllm_proxy_custom_llm_provider():
    """
    Tests force_use_hangarllm_proxy uses HANGARLLM_PROXY_API_BASE and HANGARLLM_PROXY_API_KEY from env.
    """
    test_model = "gpt-3.5-turbo"
    expected_api_base = "http://localhost:8000"
    expected_api_key = "test_proxy_key"

    with patch.dict(
        os.environ,
        {
            "HANGARLLM_PROXY_API_BASE": expected_api_base,
            "HANGARLLM_PROXY_API_KEY": expected_api_key,
        },
        clear=True,
    ):
        (
            model,
            provider,
            key,
            base,
        ) = hangarllm.HangarLLMProxyChatConfig().hangarllm_proxy_get_custom_llm_provider_info(model=test_model)

    assert model == test_model
    assert provider == "hangarllm_proxy"
    assert key == expected_api_key
    assert base == expected_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_hangarllm_proxy_with_args_override_env_vars():
    """
    Tests force_use_hangarllm_proxy uses api_base and api_key args over environment variables.
    """
    test_model = "gpt-4"
    arg_api_base = "http://custom-proxy.com"
    arg_api_key = "custom_key_from_arg"

    env_api_base = "http://env-proxy.com"
    env_api_key = "env_key"

    with patch.dict(
        os.environ,
        {"HANGARLLM_PROXY_API_BASE": env_api_base, "HANGARLLM_PROXY_API_KEY": env_api_key},
        clear=True,
    ):
        (
            model,
            provider,
            key,
            base,
        ) = hangarllm.HangarLLMProxyChatConfig().hangarllm_proxy_get_custom_llm_provider_info(
            model=test_model, api_base=arg_api_base, api_key=arg_api_key
        )

    assert model == test_model
    assert provider == "hangarllm_proxy"
    assert key == arg_api_key
    assert base == arg_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_hangarllm_proxy_model_prefix_stripping():
    """
    Tests force_use_hangarllm_proxy strips 'hangarllm_proxy/' prefix from model name.
    """
    original_model = "hangarllm_proxy/claude-2"
    expected_model = "claude-2"
    expected_api_base = "http://localhost:4000"
    expected_api_key = "proxy_secret_key"

    with patch.dict(
        os.environ,
        {
            "HANGARLLM_PROXY_API_BASE": expected_api_base,
            "HANGARLLM_PROXY_API_KEY": expected_api_key,
        },
        clear=True,
    ):
        (
            model,
            provider,
            key,
            base,
        ) = hangarllm.HangarLLMProxyChatConfig().hangarllm_proxy_get_custom_llm_provider_info(model=original_model)

    assert model == expected_model
    assert provider == "hangarllm_proxy"
    assert key == expected_api_key
    assert base == expected_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_HANGARLLM_PROXY_ALWAYS_true():
    """
    Tests get_llm_provider uses hangarllm_proxy when USE_HANGARLLM_PROXY is "True".
    """
    test_model_input = "openai/gpt-4"
    expected_model_output = "openai/gpt-4"
    proxy_api_base = "http://my-global-proxy.com"
    proxy_api_key = "global_proxy_key"

    with patch.dict(
        os.environ,
        {
            "USE_HANGARLLM_PROXY": "True",
            "HANGARLLM_PROXY_API_BASE": proxy_api_base,
            "HANGARLLM_PROXY_API_KEY": proxy_api_key,
        },
        clear=True,
    ):
        model, provider, key, base = hangarllm.get_llm_provider(model=test_model_input)

    print("get_llm_provider", model, provider, key, base)

    assert model == expected_model_output
    assert provider == "hangarllm_proxy"
    assert key == proxy_api_key
    assert base == proxy_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_HANGARLLM_PROXY_ALWAYS_true_model_prefix():
    """
    Tests get_llm_provider with USE_HANGARLLM_PROXY="True" and model prefix "hangarllm_proxy/".
    """
    test_model_input = "hangarllm_proxy/gpt-4-turbo"
    expected_model_output = "gpt-4-turbo"
    proxy_api_base = "http://another-proxy.net"
    proxy_api_key = "another_key"

    with patch.dict(
        os.environ,
        {
            "USE_HANGARLLM_PROXY": "True",
            "HANGARLLM_PROXY_API_BASE": proxy_api_base,
            "HANGARLLM_PROXY_API_KEY": proxy_api_key,
        },
        clear=True,
    ):
        model, provider, key, base = hangarllm.get_llm_provider(model=test_model_input)

    assert model == expected_model_output
    assert provider == "hangarllm_proxy"
    assert key == proxy_api_key
    assert base == proxy_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_use_proxy_arg_true():
    """
    Tests get_llm_provider uses hangarllm_proxy when use_proxy=True argument is passed.
    """
    test_model_input = "mistral/mistral-large"
    expected_model_output = "mistral/mistral-large"  # force_use_hangarllm_proxy keep the model name
    proxy_api_base = "http://my-arg-proxy.com"
    proxy_api_key = "arg_proxy_key"

    # Ensure HANGARLLM_PROXY_ALWAYS is not set or False
    with patch.dict(
        os.environ,
        {
            "HANGARLLM_PROXY_API_BASE": proxy_api_base,
            "HANGARLLM_PROXY_API_KEY": proxy_api_key,
        },
        clear=True,
    ):  # clear=True removes HANGARLLM_PROXY_ALWAYS if it was set by other tests
        model, provider, key, base = hangarllm.get_llm_provider(
            model=test_model_input,
            hangarllm_params=HangarLLM_Params(use_hangarllm_proxy=True, model=test_model_input),
        )

    assert model == expected_model_output
    assert provider == "hangarllm_proxy"
    assert key == proxy_api_key
    assert base == proxy_api_base

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
def test_get_llm_provider_use_proxy_arg_true_with_direct_args():
    """
    Tests get_llm_provider with use_proxy=True and explicit api_base/api_key args.
    These args should be passed to force_use_hangarllm_proxy and override env vars.
    """
    test_model_input = "anthropic/claude-3-opus"
    expected_model_output = "anthropic/claude-3-opus"

    arg_api_base = "http://specific-proxy-endpoint.org"
    arg_api_key = "specific_key_for_call"

    # Set some env vars to ensure they are overridden
    env_proxy_api_base = "http://env-default-proxy.com"
    env_proxy_api_key = "env_default_key"

    with patch.dict(
        os.environ,
        {
            "HANGARLLM_PROXY_API_BASE": env_proxy_api_base,
            "HANGARLLM_PROXY_API_KEY": env_proxy_api_key,
        },
        clear=True,
    ):
        model, provider, key, base = hangarllm.get_llm_provider(
            model=test_model_input,
            api_base=arg_api_base,
            api_key=arg_api_key,
            hangarllm_params=HangarLLM_Params(use_hangarllm_proxy=True, model=test_model_input),
        )

    assert model == expected_model_output
    assert provider == "hangarllm_proxy"
    assert key == arg_api_key  # Should use the argument key
    assert base == arg_api_base  # Should use the argument base

@pytest.fixture
def shipped_generalizations():
    """Install the rules shipped in the bundled backup, then restore.

    The remote-fetched cost map pinned to ``main`` may not yet carry the rule
    added on this branch, so these tests install the rule the branch actually
    ships rather than depending on whatever the live URL returns.
    """
    from hangarllm.hangarllm_core_utils.fallback_generalizations import (
        get_fallback_generalization_rules,
        set_fallback_generalizations,
    )
    from hangarllm.hangarllm_core_utils.get_model_cost_map import GetModelCostMap

    previous = list(get_fallback_generalization_rules())
    backup = GetModelCostMap.load_local_model_cost_map()
    rules = backup.get("fallback_generalizations", {}).get("rules", [])
    set_fallback_generalizations(rules)
    try:
        yield rules
    finally:
        set_fallback_generalizations(previous)

@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
class TestClaudeModelPatternMatching:
    """
    The ``anthropic-claude-ids`` fallback generalization routing rule routes future
    Claude models to the Anthropic provider without requiring a
    model_prices_and_context_window.json entry. These tests exercise the rule
    end-to-end through ``get_llm_provider`` and ``match_routing_generalization``.
    """

    @pytest.mark.parametrize(
        "model",
        [
            "claude-opus-4-9",
            "claude-opus-5-1",
            "claude-sonnet-4-6",
            "claude-sonnet-5-0",
            "claude-haiku-4-5",
            "claude-haiku-5-0",
            "claude-opus-5-1-20270101",
            "claude-sonnet-4-7-20260601",
            "claude-haiku-4-6-20251201",
            # A tier segment we don't know about today still routes: the regex
            # accepts any [a-z]+ tier rather than a hard-coded opus|sonnet|haiku
            # list, so a future tier is covered without a code change.
            "claude-mini-4-5",
            "claude-neptune-6-0",
        ],
    )
    def test_unknown_claude_routes_to_anthropic(self, model, shipped_generalizations):
        _, custom_llm_provider, _, _ = hangarllm.get_llm_provider(model=model)
        assert custom_llm_provider == "anthropic"

    @pytest.mark.parametrize(
        "model",
        [
            "gpt-4",
            "mistral-large",
            "llama-3",
            # Wrong order (variant before name)
            "claude-4-opus",
            # Missing version numbers
            "claude-opus",
            # Old format (claude-3-opus instead of claude-opus-3)
            "claude-3-opus-20240229",
        ],
    )
    def test_non_matching_models_do_not_match_rule(self, model, shipped_generalizations):
        from hangarllm.hangarllm_core_utils.fallback_generalizations import (
            match_routing_generalization,
        )

        assert match_routing_generalization(model) is None

    def test_routing_comes_from_the_rule_not_python(self, shipped_generalizations):
        """With the rule cleared, an unknown claude must no longer route to
        anthropic; this guards against re-introducing a hard-coded Python regex."""
        from hangarllm.hangarllm_core_utils.fallback_generalizations import (
            set_fallback_generalizations,
        )

        set_fallback_generalizations([])
        with pytest.raises(hangarllm.BadRequestError):
            hangarllm.get_llm_provider(model="claude-opus-4-9")


@pytest.mark.usefixtures("_vcr_outcome_gate", "isolate_hangarllm_state", "setup_and_teardown")
class TestTypesafeJevPatternMatching:
    def test_every_priced_jev_id_routes_to_typesafe(
        self, shipped_generalizations: None
    ) -> None:
        from hangarllm.hangarllm_core_utils.get_model_cost_map import GetModelCostMap

        priced_ids: Final = tuple(
            key.removeprefix("typesafe/")
            for key in GetModelCostMap.load_local_model_cost_map()
            if key.startswith("typesafe/")
        )
        assert "jev-latest" in priced_ids
        assert {
            model: hangarllm.get_llm_provider(model=model)[1] for model in priced_ids
        } == dict.fromkeys(priced_ids, "typesafe")

    @pytest.mark.parametrize(
        "model",
        [
            "foo/jev-latest",
            "openjev-latest",
            "jev-",
            "jev-latest model",
            "jev-internal-router",
            "jev-2.0-internal",
            "jev-1.0-acme.router",
            "jev-1.0",
            "jev-2.0",
            "jev-1.13",
        ],
    )
    def test_namespaced_or_partial_jev_name_does_not_match_rule(
        self, model: str, shipped_generalizations: None
    ) -> None:
        from hangarllm.hangarllm_core_utils.fallback_generalizations import (
            match_routing_generalization,
        )

        assert match_routing_generalization(model) is None


@pytest.mark.parametrize("prefix", ["openai", "anthropic", "custom_openai", "openai_like"])
def test_opencode_affinity_resolution_preserves_existing_transport(prefix: str) -> None:
    api_base: Final = "https://opencode.ai/zen/go/v1"
    model, provider, _, destination = get_llm_provider(model=f"{prefix}/test-model", api_base=api_base)
    assert (model, provider, destination) == ("test-model", prefix, api_base)
    assert get_provider_affinity_header(destination) == "x-opencode-session"


@pytest.fixture
def chatgpt_login_tripwire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    blocked: Final = tmp_path / "blocked"
    blocked.write_text("ordinary file")
    monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(blocked / "unused"))
    monkeypatch.delenv("CHATGPT_AUTH_FILE", raising=False)
    with respx.mock as transport:
        yield
        assert len(transport.calls) == 0


@pytest.mark.parametrize(
    ("model", "custom_llm_provider", "expected"),
    [
        ("chatgpt/gpt-5.4", None, ("gpt-5.4", "chatgpt")),
        ("gpt-5.4", "chatgpt", ("gpt-5.4", "chatgpt")),
        ("github_copilot/gpt-4o", None, ("gpt-4o", "github_copilot")),
        ("openai/gpt-5.4", None, ("gpt-5.4", "openai")),
    ],
)
def test_resolve_model_and_provider_for_metadata_never_logs_in(
    chatgpt_login_tripwire: None, model: str, custom_llm_provider: str | None, expected: tuple[str, str]
) -> None:
    assert resolve_model_and_provider_for_metadata(model, custom_llm_provider) == expected


def test_metadata_callers_never_log_in_for_a_declared_chatgpt_deployment(
    chatgpt_login_tripwire: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hangarllm.hangarllm_core_utils.llm_response_utils.get_api_base import get_api_base
    from hangarllm.proxy.spend_tracking.savings import _resolve_model
    from hangarllm.router import Router
    from hangarllm.utils import supports_native_streaming

    monkeypatch.setenv("HANGARLLM_LOCAL_MODEL_COST_MAP", "True")

    assert supports_native_streaming("chatgpt/gpt-5.4", None) is True
    assert get_api_base("chatgpt/gpt-5.4", {"model": "chatgpt/gpt-5.4"}) == "https://chatgpt.com/backend-api/codex"
    identity = _resolve_model("chatgpt/gpt-5.4", None)
    assert identity is not None and identity.provider == "chatgpt"
    group = Router(model_list=[{"model_name": "codex", "hangarllm_params": {"model": "chatgpt/gpt-5.4"}}]).registry().group(
        "codex"
    )
    assert group is not None and group.providers == ["chatgpt"]
