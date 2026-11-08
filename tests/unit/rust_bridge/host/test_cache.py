from typing import Final

import pytest

import hangarllm
from hangarllm.caching.caching import Cache
from hangarllm.rust_bridge.host.cache import configured_cache
from hangarllm.types.caching import HangarLLMCacheType


def test_configured_cache_preserves_identity_and_observes_runtime_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    initial: Final = Cache(type=HangarLLMCacheType.LOCAL)
    replacement: Final = Cache(type=HangarLLMCacheType.LOCAL)
    monkeypatch.setattr(hangarllm, "cache", initial)
    assert configured_cache() is initial

    monkeypatch.setattr(hangarllm, "cache", replacement)
    assert configured_cache() is replacement

    monkeypatch.setattr(hangarllm, "cache", None)
    assert configured_cache() is None
