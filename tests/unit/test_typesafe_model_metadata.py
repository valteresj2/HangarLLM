import pytest

import hangarllm


@pytest.fixture(autouse=True)
def local_model_cost_map(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HANGARLLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setattr(hangarllm, "model_cost", hangarllm.get_model_cost_map(url=""))


def test_typesafe_models_share_pricing_and_provider_metadata():
    models = ("jev-1.13.0", "jev-1.14.0", "jev-latest", "jev-preview")
    entries = [hangarllm.model_cost[f"typesafe/{model}"] for model in models]

    assert {entry["input_cost_per_token"] for entry in entries} == {entries[0]["input_cost_per_token"]}
    assert {entry["output_cost_per_token"] for entry in entries} == {entries[0]["output_cost_per_token"]}
    assert {entry["hangarllm_provider"] for entry in entries} == {"typesafe"}
    assert {entry["max_input_tokens"] for entry in entries} == {entries[0]["max_input_tokens"]}
