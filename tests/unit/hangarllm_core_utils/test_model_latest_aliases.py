from typing import Final

import pytest

import hangarllm
from hangarllm.hangarllm_core_utils.model_latest_aliases import (
    expand_model_latest_alias,
    get_model_latest_aliases,
    is_model_latest_alias,
)


@pytest.mark.parametrize("model", ("", "gpt-luna-latest", "openai/unknown", "gemini/gemini-pro-latest"))
def test_non_alias_expansion_keeps_the_requested_name(model: str) -> None:
    assert expand_model_latest_alias(model) == (model,)


def test_alias_expansion_keeps_requested_and_target_names() -> None:
    for provider, aliases in get_model_latest_aliases().items():
        for alias, target in aliases.items():
            assert expand_model_latest_alias(f"{provider}/{alias}") == (f"{provider}/{alias}", f"{provider}/{target}")


def test_latest_alias_targets_have_chat_pricing_without_shadowing_native_models() -> None:
    for provider, aliases in get_model_latest_aliases().items():
        for alias, target in aliases.items():
            target_key: Final = f"{provider}/{target}" if f"{provider}/{target}" in hangarllm.model_cost else target
            entry: Final = hangarllm.model_cost[target_key]
            assert (entry["hangarllm_provider"], entry["mode"]) == (provider, "chat")
            assert f"{provider}/{alias}" not in hangarllm.model_cost
            assert hangarllm.model_cost.get(alias, {}).get("hangarllm_provider") != provider
            assert hangarllm.get_llm_provider(f"{provider}/{alias}")[:2] == (target, provider)


@pytest.mark.parametrize(
    ("model", "provider", "expected"),
    (
        ("openai/gpt-luna-latest", None, True),
        ("gpt-luna-latest", "openai", True),
        ("gpt-luna-latest", None, False),
        ("gemini/gemini-pro-latest", None, False),
        ("", None, False),
        ("openai/unknown-model", None, False),
    ),
)
def test_latest_alias_detection_requires_an_explicit_provider(model: str, provider: str | None, expected: bool) -> None:
    assert is_model_latest_alias(model, provider) is expected
