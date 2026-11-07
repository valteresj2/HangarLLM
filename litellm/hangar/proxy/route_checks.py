"""
Node-role route toggles.

Split one HangarLLM deployment into an *admin* plane and a *data* plane:

* ``DISABLE_LLM_API_ENDPOINTS=true``  - this node serves management routes only
  (model listing stays available so the console can render).
* ``DISABLE_ADMIN_ENDPOINTS=true``    - this node serves LLM traffic only.
"""

from typing import Final

from fastapi import HTTPException, status

from litellm.secret_managers.main import get_secret_bool

_ALWAYS_ALLOWED_WITH_LLM_DISABLED: Final = frozenset({"/models", "/v1/models"})


class HangarRouteChecks:
    @staticmethod
    def is_llm_api_route_disabled() -> bool:
        return get_secret_bool("DISABLE_LLM_API_ENDPOINTS") is True

    @staticmethod
    def is_management_routes_disabled() -> bool:
        return get_secret_bool("DISABLE_ADMIN_ENDPOINTS") is True

    @staticmethod
    def should_call_route(route: str) -> None:
        from litellm.proxy.auth.route_checks import RouteChecks

        if RouteChecks.is_management_route(route=route) and HangarRouteChecks.is_management_routes_disabled():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Management routes are disabled for this instance.",
            )
        if (
            route not in _ALWAYS_ALLOWED_WITH_LLM_DISABLED
            and RouteChecks.is_llm_api_route(route=route)
            and HangarRouteChecks.is_llm_api_route_disabled()
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="LLM API routes are disabled for this instance.",
            )


EnterpriseRouteChecks = HangarRouteChecks
