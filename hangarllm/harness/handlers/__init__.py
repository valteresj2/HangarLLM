"""Handlers run a harness config: CLI runtimes and in-process harnesses."""

from __future__ import annotations

from hangarllm.harness.errors import HarnessError
from hangarllm.harness.handlers.base import BaseHarnessHandler
from hangarllm.harness.types import Harness, require_harness
from hangarllm.llms.base_llm.harness.transformation import (
    BaseCLIHarnessConfig,
    BaseHarnessConfig,
)
from hangarllm.utils import ProviderConfigManager


def get_harness_config(harness: Harness) -> BaseHarnessConfig:
    config = ProviderConfigManager.get_provider_harness_config(require_harness(harness))
    if config is None:
        raise HarnessError(f"No harness config registered for Harness.{harness.name}")
    return config


def get_harness_handler(config: BaseHarnessConfig) -> BaseHarnessHandler:
    """The handler that knows how to run this kind of config."""
    if isinstance(config, BaseCLIHarnessConfig):
        from hangarllm.harness.handlers.cli_handler import CLIHarnessHandler

        return CLIHarnessHandler(config)
    if config.harness is Harness.DEEPAGENTS:
        from hangarllm.harness.handlers.deepagents_handler import DeepAgentsHandler

        return DeepAgentsHandler(config)
    if config.harness is Harness.TOOL_LOOP:
        from hangarllm.harness.handlers.tool_loop_handler import ToolLoopHandler

        return ToolLoopHandler(config)
    raise HarnessError(f"No handler for Harness.{config.harness.name}")


__all__ = ("BaseHarnessHandler", "get_harness_config", "get_harness_handler")
