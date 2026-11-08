"""Lists the Decisions wire formats an admin can assign to a model."""

from typing import Annotated, Final, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from hangarllm.hangar.decisions.formats import available_decisions_formats
from hangarllm.hangar.proxy._auth import require_proxy_admin_or_viewer
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth

router: Final = APIRouter(tags=["decisions"])


class DecisionsFormat(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    source: Literal["builtin", "custom"]


class DecisionsFormatList(BaseModel):
    model_config = ConfigDict(frozen=True)

    formats: tuple[DecisionsFormat, ...]


@router.get("/decisions/formats", response_model=DecisionsFormatList)
async def list_decisions_formats(
    caller: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> DecisionsFormatList:
    require_proxy_admin_or_viewer(caller)
    return DecisionsFormatList(
        formats=tuple(
            DecisionsFormat(name=item.name, description=item.description, source=item.source)
            for item in available_decisions_formats()
        )
    )
