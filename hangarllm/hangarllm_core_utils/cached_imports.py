"""
Cached imports module for HangarLLM.

This module provides cached import functionality to avoid repeated imports
inside functions that are critical to performance.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

# Type annotations for cached imports
if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.coroutine_checker import CoroutineChecker
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging

# Global cache variables
_HangarLLMLogging: type["Logging"] | None = None
_coroutine_checker: Optional["CoroutineChecker"] = None
_set_callbacks: Callable | None = None


def get_hangarllm_logging_class() -> type["Logging"]:
    """Get the cached HangarLLM Logging class, initializing if needed."""
    global _HangarLLMLogging
    if _HangarLLMLogging is not None:
        return _HangarLLMLogging
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging

    _HangarLLMLogging = Logging
    return _HangarLLMLogging


def get_coroutine_checker() -> "CoroutineChecker":
    """Get the cached coroutine checker instance, initializing if needed."""
    global _coroutine_checker
    if _coroutine_checker is not None:
        return _coroutine_checker
    from hangarllm.hangarllm_core_utils.coroutine_checker import coroutine_checker

    _coroutine_checker = coroutine_checker
    return _coroutine_checker


def get_set_callbacks() -> Callable:
    """Get the cached set_callbacks function, initializing if needed."""
    global _set_callbacks
    if _set_callbacks is not None:
        return _set_callbacks
    from hangarllm.hangarllm_core_utils.hangarllm_logging import set_callbacks

    _set_callbacks = set_callbacks
    return _set_callbacks


def clear_cached_imports() -> None:
    """Clear all cached imports. Useful for testing or memory management."""
    global _HangarLLMLogging, _coroutine_checker, _set_callbacks
    _HangarLLMLogging = None
    _coroutine_checker = None
    _set_callbacks = None
