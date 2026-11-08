"""Guardrail translation mapping for MCP tool calls."""

from typing import Final

from hangarllm.proxy.mcp_server.guardrail_translation.handler import (
    MCPGuardrailTranslationHandler,
)
from hangarllm.types.utils import CallTypes

# This mapping lives alongside the MCP server implementation because MCP
# integrations are managed by the proxy subsystem, not hangarllm.llms providers.
# Unified guardrails import this module explicitly to register the handler.

guardrail_translation_mappings: Final = {
    CallTypes.call_mcp_tool: MCPGuardrailTranslationHandler,
    CallTypes.list_mcp_tools: MCPGuardrailTranslationHandler,
}

__all__ = ["MCPGuardrailTranslationHandler", "guardrail_translation_mappings"]
