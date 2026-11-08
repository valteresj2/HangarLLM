import pytest

import hangarllm


@pytest.fixture
def local_model_cost_map(monkeypatch):
    original_model_cost = hangarllm.model_cost
    monkeypatch.setenv("HANGARLLM_LOCAL_MODEL_COST_MAP", "True")
    hangarllm.model_cost = hangarllm.get_model_cost_map(url="")
    hangarllm.get_model_info.cache_clear()
    try:
        yield
    finally:
        hangarllm.model_cost = original_model_cost
        hangarllm.get_model_info.cache_clear()


def test_reasoning_effort_stays_unsupported_on_vertex_partner_models(local_model_cost_map):
    assert "reasoning_effort" in hangarllm.get_supported_openai_params(
        model="mistral-medium-3", custom_llm_provider="mistral"
    )
    assert "reasoning_effort" not in hangarllm.get_supported_openai_params(
        model="mistral-medium-3", custom_llm_provider="vertex_ai"
    )
    dropped = hangarllm.get_optional_params(
        model="mistral-medium-3",
        custom_llm_provider="vertex_ai",
        reasoning_effort="high",
        drop_params=True,
    )
    assert "reasoning_effort" not in dropped
