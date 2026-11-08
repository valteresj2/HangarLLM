"""Typed, provenance-aware resolution of proxy settings from DB then env."""

from hangarllm.proxy.config_resolvers._descriptors import (
    FieldDescriptor,
    FieldSource,
    resolve_fields,
)
from hangarllm.proxy.config_resolvers.settings_store import (
    SettingsStore,
    config_ownership_message,
    source_for,
)

__all__ = (
    "FieldDescriptor",
    "FieldSource",
    "SettingsStore",
    "config_ownership_message",
    "resolve_fields",
    "source_for",
)
