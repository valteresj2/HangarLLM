"""Force ``hangarllm.model_cost`` to load from the PR-local JSON for these tests.

By default ``hangarllm.model_cost`` is fetched from the main branch on GitHub,
which lags behind PR-branch flag additions. This fixture loads the local
file so per-model flag tests pass in CI as well as locally.
See upstream issue 27122
"""

import pytest

import hangarllm
from hangarllm.hangarllm_core_utils.get_model_cost_map import get_model_cost_map


@pytest.fixture(autouse=True)
def _use_pr_local_model_cost_map(monkeypatch):
    monkeypatch.setenv("HANGARLLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setattr(
        hangarllm,
        "model_cost",
        get_model_cost_map(url=hangarllm.model_cost_map_url),
    )
    yield
