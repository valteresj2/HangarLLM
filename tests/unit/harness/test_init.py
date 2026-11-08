"""Tests for hangarllm/harness/__init__.py: the public API surface."""

from __future__ import annotations


from hangarllm import harness
from tests.test_hangarllm_rust.support.child_interpreter import run_child_interpreter
from hangarllm.utils import ProviderConfigManager

PUBLIC_NAMES = [
    "Harness",
    "agent",
    "aagent",
    "agent_session",
    "aagent_session",
    "agent_resume",
    "aagent_resume",
    "agent_capabilities",
    "Result",
    "Usage",
    "State",
    "Capabilities",
    "Session",
    "EventStream",
    "Text",
    "Reasoning",
    "ToolCall",
    "ToolResult",
    "FileChange",
    "Compaction",
    "Approval",
    "Done",
    "Event",
    "ClaudeCodeOptions",
    "CodexOptions",
    "OpenCodeOptions",
    "PiOptions",
    "DeepAgentsOptions",
    "ToolLoopOptions",
    "HarnessError",
    "CapabilityUnsupported",
    "OptionsMismatch",
    "HarnessInstallFailed",
    "SandboxError",
    "SessionClosed",
    "StateIncompatible",
    "OutputInvalid",
]
ERROR_NAMES = [
    "CapabilityUnsupported",
    "OptionsMismatch",
    "HarnessInstallFailed",
    "SandboxError",
    "SessionClosed",
    "StateIncompatible",
    "OutputInvalid",
]
LAZY_IMPORT_CHECK = (
    "import sys, hangarllm\n"
    "assert 'hangarllm.harness' not in sys.modules\n"
    "h = hangarllm.harness\n"
    "assert h.Harness.CODEX.value == 'codex'\n"
    "assert 'starlette' not in sys.modules and 'uvicorn' not in sys.modules\n"
    "print('ok')\n"
)


def test_public_api_names_exported():
    missing = [name for name in PUBLIC_NAMES if not hasattr(harness, name)]
    assert missing == []
    assert set(PUBLIC_NAMES) <= set(harness.__all__)


def test_errors_share_base_class():
    for name in ERROR_NAMES:
        assert issubclass(getattr(harness, name), harness.HarnessError)


def test_hangarllm_harness_attribute_is_lazy():
    out = run_child_interpreter(LAZY_IMPORT_CHECK, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"


def test_adapter_registry_paths_cover_every_harness():
    for member in harness.Harness:
        config = ProviderConfigManager.get_provider_harness_config(member)
        assert config is not None and config.harness is member


def test_hangarllm_agent_is_top_level_and_lazy():
    code = (
        "import sys, hangarllm; assert 'hangarllm.harness' not in sys.modules; "
        "assert hangarllm.agent is hangarllm.harness.agent; "
        "assert hangarllm.Harness.CODEX.value == 'codex'; "
        "assert hangarllm.ToolLoopOptions is hangarllm.harness.ToolLoopOptions"
    )
    out = run_child_interpreter(code, timeout=120)
    assert out.returncode == 0, out.stderr
