from datetime import datetime
from typing import Literal, Protocol, TypeAlias

from pydantic import ConfigDict

from hangarllm.types.llms.base import HangarLLMBaseModel

CredentialTestStatus: TypeAlias = Literal["healthy", "failing", "untested"]
CredentialTestKind: TypeAlias = Literal["model_list", "completion"]


class CredentialTestResult(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    credential_name: str | None
    status: CredentialTestStatus
    kind: CredentialTestKind | None
    http_status: int | None
    error: str | None
    latency_ms: float | None
    checked_at: datetime


class CredentialTestStore(Protocol):
    async def save_result(self, result: CredentialTestResult, provider: str, checked_by: str | None) -> None: ...

    async def latest_results(self) -> tuple[CredentialTestResult, ...]: ...
