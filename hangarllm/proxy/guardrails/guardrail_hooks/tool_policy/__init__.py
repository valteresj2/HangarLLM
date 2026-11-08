from typing import Final

import hangarllm
from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: HangarllmParams, guardrail: Guardrail):
    from hangarllm.proxy.guardrails.guardrail_hooks.tool_policy.tool_policy_guardrail import (
        ToolPolicyGuardrail,
    )

    _callback: Final = ToolPolicyGuardrail(
        guardrail_name=guardrail.get("guardrail_name", "tool_policy"),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_callback)
    return _callback
