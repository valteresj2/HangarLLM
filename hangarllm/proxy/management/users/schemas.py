from pydantic import BaseModel, ConfigDict

from hangarllm.proxy._types import HangarllmUserRoles


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    user_role: HangarllmUserRoles | None
    user_email: str | None
