from pydantic import Field

from hangarllm.types.llms.base import HangarLLMBaseModel


class AzureContentSafetyConfigModel(HangarLLMBaseModel):
    """Configuration parameters for the Azure Content Safety Prompt Shield guardrail"""

    api_key: str | None = Field(
        default=None,
        description="API key for the Azure Content Safety Prompt Shield guardrail",
    )

    api_base: str | None = Field(
        default=None,
        description="Base URL for the Azure Content Safety Prompt Shield guardrail",
    )
    api_version: str | None = Field(
        default="2024-09-01",
        description="API version for the Azure Content Safety Prompt Shield guardrail. Default is 2024-09-01",
    )
