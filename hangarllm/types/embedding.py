from pydantic import ConfigDict, Field

from hangarllm.types.llms.base import HangarLLMBaseModel


class EmbeddingRequest(HangarLLMBaseModel):
    model: str
    input: list[str] = Field(default=[])
    timeout: int = 600
    api_base: str | None = None
    api_version: str | None = None
    api_key: str | None = None
    api_type: str | None = None
    caching: bool = False
    user: str | None = None
    custom_llm_provider: str | dict | None = None
    hangarllm_call_id: str | None = None
    hangarllm_logging_obj: dict | None = None
    logger_fn: str | None = None

    model_config = ConfigDict(extra="allow")
