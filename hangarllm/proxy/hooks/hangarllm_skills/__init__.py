"""
HangarLLM Skills Hook - Proxy integration for skills

This module provides the CustomLogger hook for skills processing.
The actual skill logic is in hangarllm/llms/hangarllm_proxy/skills/.

Usage:
    from hangarllm.proxy.hooks.hangarllm_skills import SkillsInjectionHook

    # Register hook in proxy
    hangarllm.callbacks.append(SkillsInjectionHook())
"""

# Re-export from the SDK location for convenience
from hangarllm.llms.hangarllm_proxy.skills import (
    HANGARLLM_CODE_EXECUTION_TOOL,
    CodeExecutionHandler,
    HangarLLMInternalTools,
    SkillPromptInjectionHandler,
    SkillsSandboxExecutor,
    code_execution_handler,
    get_hangarllm_code_execution_tool,
)
from hangarllm.proxy.hooks.hangarllm_skills.main import SkillsInjectionHook

__all__ = [
    "HANGARLLM_CODE_EXECUTION_TOOL",
    "CodeExecutionHandler",
    "HangarLLMInternalTools",
    "SkillPromptInjectionHandler",
    "SkillsInjectionHook",
    "SkillsSandboxExecutor",
    "code_execution_handler",
    "get_hangarllm_code_execution_tool",
]
