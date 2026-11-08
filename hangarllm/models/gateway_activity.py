from typing import Literal, Protocol, TypeAlias

from pydantic import ConfigDict

from hangarllm.types.llms.base import HangarLLMBaseModel


class GatewayRouteActivity(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["route"]
    date: str
    category: str
    route: str
    successful_requests: int
    failed_requests: int


class GatewayStatusCodeActivity(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["status"]
    status_code: int
    failed_requests: int


GatewayActivity: TypeAlias = GatewayRouteActivity | GatewayStatusCodeActivity


class GatewayActivityStore(Protocol):
    async def get_activity(self, start_date: str, end_date: str) -> tuple[GatewayActivity, ...]: ...
