"""
Custom UI SSO sign-in.

When ``general_settings.custom_ui_sso_sign_in_handler`` points at a
``CustomSSOLoginHandler`` (typically reading identity headers set by an OAuth
proxy in front of HangarLLM), the console login delegates to it. The request
must come from a ``trusted_proxy_ranges`` address, so identity headers cannot be
spoofed by direct clients.
"""

from typing import Final

from fastapi import Request
from fastapi.responses import RedirectResponse


class HangarCustomSSOHandler:
    @staticmethod
    async def handle_custom_ui_sso_sign_in(request: Request) -> RedirectResponse:
        from litellm.proxy.auth.trusted_proxy_utils import require_trusted_proxy_request
        from litellm.proxy.management_endpoints.ui_sso import SSOAuthenticationHandler
        from litellm.proxy.proxy_server import general_settings, user_custom_ui_sso_sign_in_handler

        if user_custom_ui_sso_sign_in_handler is None:
            raise ValueError("custom_ui_sso_sign_in_handler is not configured")
        require_trusted_proxy_request(
            request=request,
            general_settings=general_settings,
            feature_name="Custom UI SSO",
        )
        openid: Final = await user_custom_ui_sso_sign_in_handler.handle_custom_ui_sso_sign_in(request=request)
        return await SSOAuthenticationHandler.get_redirect_response_from_openid(
            result=openid,
            request=request,
            received_response=None,
            generic_client_id=None,
            ui_access_mode=None,
        )


EnterpriseCustomSSOHandler = HangarCustomSSOHandler
