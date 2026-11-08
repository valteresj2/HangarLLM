from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hangarllm.caching.caching import Cache


def configured_cache() -> Cache | None:
    import hangarllm

    return hangarllm.cache
