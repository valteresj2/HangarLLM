from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from hangarllm.types.llms.base import HangarLLMBaseModel


class VertexGemmaContainerError(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)
    object: Literal["error"]
    message: str
    code: Annotated[int, Field(ge=400, le=599)]
