"""Choose the wire format of a Decisions deployment, and plug in new ones without touching core.

Clients always speak the OpenAI Decisions shape on ``POST /v1/decisions``. By default a deployment
uses its provider's wire format. Setting ``litellm_params.decisions_format`` picks another one by
name. A new vendor format is a subclass of ``OpenAIShapedDecisionsFormat`` registered in config:

    litellm_settings:
      decisions_formats:
        acme: acme_decisions.format_instance
"""

import inspect
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Final

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.llms.base_llm.decisions.transformation import BaseDecisionsConfig, UnsupportedDecisionsRequest
from litellm.llms.openai.decisions.transformation import OpenAIDecisionsConfig
from litellm.types.decisions import DecisionsIRRequest, DecisionsIRResponse

AUTO_FORMAT: Final = "auto"
_NAME: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


@dataclass(frozen=True, slots=True)
class DecisionsFormatInfo:
    name: str
    description: str
    source: str


@dataclass(frozen=True, slots=True)
class _Builtin:
    module: str
    attribute: str
    description: str


_BUILTINS: Final[Mapping[str, _Builtin]] = {
    "openai": _Builtin(
        "litellm.llms.openai.decisions.transformation",
        "OpenAIDecisionsConfig",
        "OpenAI Decisions: POST /v1/decisions with input and a questions array",
    ),
    "openrouter": _Builtin(
        "litellm.llms.openrouter.decisions.transformation",
        "OpenRouterDecisionsConfig",
        "OpenRouter Decisions: POST /alpha/decisions",
    ),
    "systemone": _Builtin(
        "litellm.llms.typesafe.decisions.transformation",
        "TypeSafeDecisionsConfig",
        "System One: state plus keyed questions",
    ),
}


class OpenAIShapedDecisionsFormat(OpenAIDecisionsConfig):
    """Base for custom formats: convert to and from the OpenAI Decisions JSON, nothing else.

    ``path`` is the upstream route. Override ``description`` so admins can tell formats apart.
    """

    description: str = ""

    def to_wire(self, body: Mapping[str, object]) -> Mapping[str, object]:
        return body

    def from_wire(self, payload: object) -> object:
        return payload

    def transform_decisions_request(
        self, model: str, request: DecisionsIRRequest, custom_llm_provider: str
    ) -> Mapping[str, object] | UnsupportedDecisionsRequest:
        body: Final = super().transform_decisions_request(model, request, custom_llm_provider)
        return body if isinstance(body, UnsupportedDecisionsRequest) else self.to_wire(body)

    def parse_response(self, payload: object, request: DecisionsIRRequest) -> DecisionsIRResponse:
        return super().parse_response(self.from_wire(payload), request)


_registered: dict[str, BaseDecisionsConfig] = {}  # mutable-ok: process-wide plugin registry
_loaded: dict[tuple[str, str], BaseDecisionsConfig] = {}  # mutable-ok: configured plugins, built once


def _as_config(value: object, name: str) -> BaseDecisionsConfig:
    built: Final = value() if inspect.isclass(value) else value
    if not isinstance(built, BaseDecisionsConfig):
        raise TypeError(f"Decisions format '{name}' must be a BaseDecisionsConfig, got {type(built).__name__}")
    return built


def register_decisions_format(name: str, config: BaseDecisionsConfig | type[BaseDecisionsConfig]) -> None:
    if _NAME.fullmatch(name) is None or name == AUTO_FORMAT:
        raise ValueError(f"Invalid Decisions format name: '{name}'")
    _registered[name] = _as_config(config, name)


def _configured_paths() -> Mapping[str, str]:
    configured: Final = getattr(litellm, "decisions_formats", None)
    if not isinstance(configured, Mapping):
        return {}
    return {name: path for name, path in configured.items() if isinstance(name, str) and isinstance(path, str)}


def _load_configured(name: str, path: str) -> BaseDecisionsConfig | None:
    cached: Final = _loaded.get((name, path))
    if cached is not None:
        return cached
    from litellm.proxy.proxy_server import user_config_file_path
    from litellm.proxy.types_utils.utils import get_instance_fn

    try:
        config: Final = _as_config(get_instance_fn(path, config_file_path=user_config_file_path), name)
    except (ImportError, AttributeError, TypeError, ValueError) as error:
        verbose_proxy_logger.error("Could not load Decisions format '%s' from %s: %s", name, path, error)
        return None
    _loaded[(name, path)] = config
    return config


def resolve_decisions_format(name: str) -> BaseDecisionsConfig | None:
    """The format registered under ``name``. Only names resolve, never import paths."""
    if name in _registered:
        return _registered[name]
    path: Final = _configured_paths().get(name)
    if path is not None:
        return _load_configured(name, path)
    builtin: Final = _BUILTINS.get(name)
    if builtin is None:
        return None
    return _as_config(getattr(import_module(builtin.module), builtin.attribute), name)


def available_decisions_formats() -> tuple[DecisionsFormatInfo, ...]:
    builtin: Final = tuple(DecisionsFormatInfo(n, b.description, "builtin") for n, b in _BUILTINS.items())
    plugin_names: Final = sorted({*_registered, *_configured_paths()} - set(_BUILTINS))
    resolved: Final = ((n, resolve_decisions_format(n)) for n in plugin_names)
    custom: Final = tuple(
        DecisionsFormatInfo(n, str(getattr(config, "description", "")), "custom")
        for n, config in resolved
        if config is not None
    )
    return (*builtin, *custom)


def reset_decisions_formats() -> None:
    _registered.clear()
    _loaded.clear()
