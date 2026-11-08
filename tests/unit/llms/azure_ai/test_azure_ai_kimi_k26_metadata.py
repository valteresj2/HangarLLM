"""
Test Azure AI Kimi K2.6 model metadata.
"""

import json
from importlib.resources import files

import pytest


@pytest.fixture(scope="module")
def use_local_model_cost_map():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("HANGARLLM_LOCAL_MODEL_COST_MAP", "True")

    import hangarllm
    from hangarllm.utils import _invalidate_model_cost_lowercase_map

    original_model_cost = hangarllm.model_cost
    hangarllm.model_cost = json.loads(
        files("hangarllm")
        .joinpath("model_prices_and_context_window_backup.json")
        .read_text(encoding="utf-8")
    )
    hangarllm.get_model_info.cache_clear()
    _invalidate_model_cost_lowercase_map()
    try:
        yield hangarllm
    finally:
        hangarllm.model_cost = original_model_cost
        hangarllm.get_model_info.cache_clear()
        _invalidate_model_cost_lowercase_map()
        monkeypatch.undo()


