from hangarllm.types.llms.base import HangarLLMBaseModel

from .arize import Protocol


class ArizePhoenixConfig(HangarLLMBaseModel):
    otlp_auth_headers: str | None = None
    protocol: Protocol
    endpoint: str
    project_name: str | None = None
