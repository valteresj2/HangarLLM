"""
Per-request callback controls.

A caller can switch off individual logging integrations for one request, either
with the ``x-litellm-disable-callbacks`` (or ``x-hangarllm-disable-callbacks``)
header - a comma separated list of callback names - or with
``litellm_disabled_callbacks`` in the request body / key metadata, which reaches
the logging layer as ``StandardCallbackDynamicParams['litellm_disabled_callbacks']``.

Operators can turn the feature off globally with
``litellm_settings.allow_dynamic_callback_disabling: false``.
"""

from collections.abc import Iterable, Mapping
from typing import Final

import litellm
from litellm._logging import verbose_logger
from litellm.constants import X_LITELLM_DISABLE_CALLBACKS
from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils.llm_request_utils import get_proxy_server_request_headers
from litellm.types.utils import StandardCallbackDynamicParams

X_HANGARLLM_DISABLE_CALLBACKS: Final = "x-hangarllm-disable-callbacks"
_HEADER_NAMES: Final = (X_LITELLM_DISABLE_CALLBACKS, X_HANGARLLM_DISABLE_CALLBACKS)


def _normalise(names: Iterable[object]) -> frozenset[str]:
    return frozenset(name.strip().lower() for name in names if isinstance(name, str) and name.strip())


def _header_value(headers: Mapping[str, object]) -> str | None:
    lowered: Final = {str(k).lower(): v for k, v in headers.items()}
    for name in _HEADER_NAMES:
        value = lowered.get(name)
        if isinstance(value, str):
            return value
    return None


class HangarCallbackControls:
    @staticmethod
    def _should_allow_dynamic_callback_disabling() -> bool:
        """Operators can switch the feature off; HangarLLM never gates it behind a license."""
        return litellm.allow_dynamic_callback_disabling is True

    @staticmethod
    def get_disabled_callbacks(
        litellm_params: Mapping[str, object] | None,
        standard_callback_dynamic_params: StandardCallbackDynamicParams | Mapping[str, object] | None,
    ) -> frozenset[str]:
        """Names (lower-cased) of the callbacks this request asked to skip. Header wins over body."""
        headers: Final = get_proxy_server_request_headers(dict(litellm_params) if litellm_params else None)
        header: Final = _header_value(headers) if isinstance(headers, Mapping) else None
        if header is not None:
            return _normalise(header.split(","))
        dynamic: Final = standard_callback_dynamic_params or {}
        from_body: Final = dynamic.get("litellm_disabled_callbacks") if isinstance(dynamic, Mapping) else None
        if isinstance(from_body, (list, tuple, set, frozenset)):
            return _normalise(from_body)
        if isinstance(from_body, str):
            return _normalise(from_body.split(","))
        return frozenset()

    @staticmethod
    def _callback_names(callback: object) -> frozenset[str]:
        if isinstance(callback, str):
            return frozenset({callback.lower()})
        names: set[str] = set()  # mutable-ok: accumulates registry aliases
        if isinstance(callback, CustomLogger):
            from litellm.litellm_core_utils.custom_logger_registry import CustomLoggerRegistry

            names.update(
                name.lower() for name in CustomLoggerRegistry.get_all_callback_strs_from_class_type(type(callback))
            )
            callback_name = getattr(callback, "callback_name", None)
            if isinstance(callback_name, str):
                names.add(callback_name.lower())
        else:
            fn_name = getattr(callback, "__name__", None)
            if isinstance(fn_name, str):
                names.add(fn_name.lower())
        return frozenset(names)

    @staticmethod
    def is_callback_disabled_dynamically(
        callback: object,
        litellm_params: Mapping[str, object] | None,
        standard_callback_dynamic_params: StandardCallbackDynamicParams | Mapping[str, object] | None,
    ) -> bool:
        """True when this request disabled ``callback`` (string name or logger instance)."""
        try:
            disabled: Final = HangarCallbackControls.get_disabled_callbacks(
                litellm_params, standard_callback_dynamic_params
            )
            if not disabled:
                return False
            if not HangarCallbackControls._should_allow_dynamic_callback_disabling():
                return False
            matched: Final = HangarCallbackControls._callback_names(callback) & disabled
            if matched:
                verbose_logger.debug("HangarLLM: callback %s disabled for this request", sorted(matched))
            return bool(matched)
        except Exception as e:  # noqa: BLE001 - never break logging because of a malformed header
            verbose_logger.debug("HangarLLM: unable to evaluate dynamic callback controls - %s", e)
            return False


# upstream-compatible name used by litellm_logging.py
EnterpriseCallbackControls = HangarCallbackControls
