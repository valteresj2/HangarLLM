"""
The router's configuration, built outside the router.

``RouterConfig`` is static: the constructor arguments, frozen for the router's life.
``RouterDynamicConfig`` is a snapshot of the process settings the router reads while it serves
(``hangarllm.num_retries``, ``hangarllm.model_cost``, the fallback lists, ...). A call reads one snapshot
at its start. This module is the only router code that reads ``hangarllm.*`` settings.
"""

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import TypeAdapter

import hangarllm

if TYPE_CHECKING:
    from hangarllm.caching.caching import Cache
    from hangarllm.hangarllm_core_utils.logging_callback_manager import LoggingCallbackManager


@dataclass(frozen=True, slots=True)
class RouterConfig:
    """The arguments the router was built with, exactly as passed (unset ones are absent)."""

    arguments: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def get(self, name: str, default: object = None) -> object:
        return self.arguments.get(name, default)


@dataclass(frozen=True, slots=True)
class RouterDynamicConfig:
    """Process settings the router reads per call. Values are the live objects, not copies."""

    version: int
    num_retries: int | None
    max_fallbacks: int | None
    router_max_fallbacks: int
    allowed_fails: int
    request_timeout: float
    fallbacks: Sequence[object] | None
    default_fallbacks: Sequence[str] | None
    context_window_fallbacks: Sequence[object] | None
    content_policy_fallbacks: Sequence[object] | None
    drop_params: bool | None
    disable_token_counter: bool
    provider_list: Sequence[str]
    expose_router_debug_in_errors: bool
    redact_user_api_key_info: bool | None
    model_alias_map: Mapping[str, str]
    model_cost: Mapping[str, object]
    known_custom_logger_compatible_callbacks: Sequence[str]
    exception_types: Sequence[type[BaseException]]
    callbacks: Sequence[object]
    success_callback: Sequence[object]
    failure_callback: Sequence[object]
    input_callback: Sequence[object]
    callback_manager: "LoggingCallbackManager"
    cache: "Cache | None"


_versions: Final = itertools.count(1)


def detached(value: object) -> object:
    """``value`` with its plain containers (dict, list, tuple, set) copied, all the way down, so the
    caller's own objects can't change the router afterwards. Other objects (clients, caches,
    callbacks, pydantic models) are kept as they are."""
    if isinstance(value, dict):
        return {key: detached(item) for key, item in value.items()}
    if isinstance(value, list):
        return [detached(item) for item in value]
    if isinstance(value, tuple) and type(value) is tuple:
        return tuple(detached(item) for item in value)
    if isinstance(value, set):
        return {detached(item) for item in value}
    return value


def build_router_config(arguments: Mapping[str, object]) -> RouterConfig:
    """The constructor arguments, detached from the caller's objects: settings are static.

    A bool `cooldown_time` is refused: `True` is not a number of seconds, and
    reading it as 1 s or as the default would both be a guess."""
    if isinstance(arguments.get("cooldown_time"), bool):
        raise TypeError("Router cooldown_time must be a number of seconds, not a bool")
    return RouterConfig(arguments=MappingProxyType({name: detached(value) for name, value in arguments.items()}))


def current_dynamic_config() -> RouterDynamicConfig:
    """A snapshot of the process settings as they are right now."""
    return RouterDynamicConfig(
        version=next(_versions),
        num_retries=hangarllm.num_retries,
        max_fallbacks=hangarllm.max_fallbacks,
        router_max_fallbacks=hangarllm.ROUTER_MAX_FALLBACKS,
        allowed_fails=hangarllm.allowed_fails,
        request_timeout=hangarllm.request_timeout,
        fallbacks=hangarllm.fallbacks,
        default_fallbacks=hangarllm.default_fallbacks,
        context_window_fallbacks=hangarllm.context_window_fallbacks,
        content_policy_fallbacks=hangarllm.content_policy_fallbacks,
        drop_params=hangarllm.drop_params,
        disable_token_counter=hangarllm.disable_token_counter,
        provider_list=hangarllm.provider_list,
        expose_router_debug_in_errors=hangarllm.expose_router_debug_in_errors,
        redact_user_api_key_info=hangarllm.redact_user_api_key_info,
        model_alias_map=hangarllm.model_alias_map,
        model_cost=hangarllm.model_cost,
        known_custom_logger_compatible_callbacks=hangarllm._known_custom_logger_compatible_callbacks,
        exception_types=hangarllm.HANGARLLM_EXCEPTION_TYPES,
        callbacks=hangarllm.callbacks,
        success_callback=hangarllm.success_callback,
        failure_callback=hangarllm.failure_callback,
        input_callback=hangarllm.input_callback,
        callback_manager=hangarllm.logging_callback_manager,
        cache=hangarllm.cache,
    )


_LIVE_VALUE: Final = TypeAdapter(object)
_LIVE_SOURCES: Final = MappingProxyType(
    {
        "num_retries": "num_retries",
        "max_fallbacks": "max_fallbacks",
        "router_max_fallbacks": "ROUTER_MAX_FALLBACKS",
        "allowed_fails": "allowed_fails",
        "request_timeout": "request_timeout",
        "fallbacks": "fallbacks",
        "default_fallbacks": "default_fallbacks",
        "context_window_fallbacks": "context_window_fallbacks",
        "content_policy_fallbacks": "content_policy_fallbacks",
        "drop_params": "drop_params",
        "disable_token_counter": "disable_token_counter",
        "provider_list": "provider_list",
        "expose_router_debug_in_errors": "expose_router_debug_in_errors",
        "redact_user_api_key_info": "redact_user_api_key_info",
        "model_alias_map": "model_alias_map",
        "model_cost": "model_cost",
        "known_custom_logger_compatible_callbacks": "_known_custom_logger_compatible_callbacks",
        "exception_types": "HANGARLLM_EXCEPTION_TYPES",
        "callbacks": "callbacks",
        "success_callback": "success_callback",
        "failure_callback": "failure_callback",
        "input_callback": "input_callback",
        "callback_manager": "logging_callback_manager",
        "cache": "cache",
    }
)


class LiveDynamicConfig:
    """``RouterDynamicConfig``'s fields read from the process settings at access time, with no snapshot."""

    __slots__ = ()

    def __getattr__(self, name: str) -> object:
        source: Final = _LIVE_SOURCES.get(name)
        if source is None:
            raise AttributeError(name)
        return _LIVE_VALUE.validate_python(getattr(hangarllm, source))


live_dynamic_config: Final = LiveDynamicConfig()
