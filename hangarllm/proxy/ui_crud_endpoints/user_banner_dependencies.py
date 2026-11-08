from collections.abc import Coroutine
from typing import Annotated, Protocol, TypeAlias

from fastapi import Depends

from hangarllm.models.user_banner import UserBanner
from hangarllm.proxy._types import HangarllmTableNames, UserAPIKeyAuth
from hangarllm.repositories.user_banner_repository import USER_BANNER_ROW_ID


class UserBannerAudit(Protocol):
    def __call__(self, before: UserBanner, after: UserBanner, user: UserAPIKeyAuth) -> Coroutine[None, None, None]: ...


async def get_user_banner_audit() -> UserBannerAudit:
    from hangarllm.proxy.proxy_server import create_config_audit_log

    async def audit(before: UserBanner, after: UserBanner, user: UserAPIKeyAuth) -> None:
        await create_config_audit_log(
            param_name=USER_BANNER_ROW_ID,
            action="updated",
            before_value=before.model_dump(),
            after_value=after.model_dump(),
            user_api_key_dict=user,
            table_name=HangarllmTableNames.UI_SETTINGS_TABLE_NAME,
        )

    return audit


UserBannerAuditDep: TypeAlias = Annotated[UserBannerAudit, Depends(get_user_banner_audit)]
