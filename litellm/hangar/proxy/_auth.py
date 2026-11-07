"""Small authorization helpers shared by HangarLLM management endpoints."""

from typing import Final

from fastapi import HTTPException, status

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth

_ADMIN_ROLES: Final = frozenset({LitellmUserRoles.PROXY_ADMIN.value})
_VIEW_ROLES: Final = frozenset({LitellmUserRoles.PROXY_ADMIN.value, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY.value})


def _role(user_api_key_dict: UserAPIKeyAuth) -> str | None:
    role: Final = user_api_key_dict.user_role
    return role.value if isinstance(role, LitellmUserRoles) else role


def require_proxy_admin(user_api_key_dict: UserAPIKeyAuth) -> None:
    if _role(user_api_key_dict) not in _ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "Only proxy admins can do this."})


def require_proxy_admin_or_viewer(user_api_key_dict: UserAPIKeyAuth) -> None:
    if _role(user_api_key_dict) not in _VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"error": "Only proxy admins and admin viewers can do this."}
        )


def require_db():
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "No database connected. Set DATABASE_URL to use this endpoint."},
        )
    return prisma_client
