"""
Cost calculator for A2A (Agent-to-Agent) calls.

Supports dynamic cost parameters that allow platform owners
to define custom costs per agent query or per token.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, SupportsFloat, SupportsIndex

from typing_extensions import Buffer

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import (
        Logging as HangarllmLoggingObject,
    )
else:
    HangarllmLoggingObject = Any


def _custom_response_cost(model_call_details: Mapping[str, object]) -> float | None:
    response_cost: Final = model_call_details.get("response_cost", None)
    if response_cost is None:
        return None
    if isinstance(response_cost, (str, Buffer, SupportsFloat, SupportsIndex)):
        return float(response_cost)
    raise TypeError(f"float() argument must be a string or a real number, not {type(response_cost).__name__!r}")


class A2ACostCalculator:
    @staticmethod
    def calculate_a2a_cost(
        hangarllm_logging_obj: HangarllmLoggingObject | None,
    ) -> float:
        """
        Calculate the cost of an A2A send_message call.

        Supports multiple cost parameters for platform owners:
        - cost_per_query: Fixed cost per query
        - input_cost_per_token + output_cost_per_token: Token-based pricing

        Priority order:
        1. response_cost - if set directly (backward compatibility)
        2. cost_per_query - fixed cost per query
        3. input_cost_per_token + output_cost_per_token - token-based cost
        4. Default to 0.0

        Args:
            hangarllm_logging_obj: The HangarLLM logging object containing call details

        Returns:
            float: The cost of the A2A call
        """
        if hangarllm_logging_obj is None:
            return 0.0

        model_call_details: Final = hangarllm_logging_obj.model_call_details

        # Check if user set a custom response cost (backward compatibility)
        custom_response_cost: Final = _custom_response_cost(model_call_details)
        if custom_response_cost is not None:
            return custom_response_cost

        # Get hangarllm_params for cost parameters
        hangarllm_params: Final = model_call_details.get("hangarllm_params", {}) or {}

        # Check for cost_per_query (fixed cost per query)
        if hangarllm_params.get("cost_per_query") is not None:
            return float(hangarllm_params["cost_per_query"])

        # Check for token-based pricing
        input_cost_per_token: Final = hangarllm_params.get("input_cost_per_token")
        output_cost_per_token: Final = hangarllm_params.get("output_cost_per_token")

        if input_cost_per_token is not None or output_cost_per_token is not None:
            return A2ACostCalculator._calculate_token_based_cost(
                model_call_details=model_call_details,
                input_cost_per_token=input_cost_per_token,
                output_cost_per_token=output_cost_per_token,
            )

        # Default to 0.0 for A2A calls
        return 0.0

    @staticmethod
    def _calculate_token_based_cost(
        model_call_details: dict,
        input_cost_per_token: float | None,
        output_cost_per_token: float | None,
    ) -> float:
        """
        Calculate cost based on token usage and per-token pricing.

        Args:
            model_call_details: The model call details containing usage
            input_cost_per_token: Cost per input token (can be None, defaults to 0)
            output_cost_per_token: Cost per output token (can be None, defaults to 0)

        Returns:
            float: The calculated cost
        """
        # Get usage from model_call_details
        usage: Final = model_call_details.get("usage")
        if usage is None:
            return 0.0

        # Get token counts
        prompt_tokens: Final = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens: Final = getattr(usage, "completion_tokens", 0) or 0

        # Calculate costs
        input_cost: Final = prompt_tokens * (float(input_cost_per_token) if input_cost_per_token else 0.0)
        output_cost: Final = completion_tokens * (float(output_cost_per_token) if output_cost_per_token else 0.0)

        return input_cost + output_cost
