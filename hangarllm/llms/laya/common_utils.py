from collections.abc import Mapping
from typing import Final

from pydantic import TypeAdapter, ValidationError

from hangarllm.types.llms.base import HangarLLMBaseModel


class _LayaRouting(HangarLLMBaseModel):
    model: str | None = None


def laya_response_model(response: Mapping[str, object], requested_model: str | None) -> str:
    try:
        routing: Final = TypeAdapter(_LayaRouting).validate_python(response.get("routing") or _LayaRouting())
    except ValidationError:
        return requested_model or "unknown"
    return routing.model or requested_model or "unknown"
