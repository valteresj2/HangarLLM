"""
Proxy Authentication module for HangarLLM SDK.

This module provides OAuth2/JWT token management for authenticating
with HangarLLM Proxy or any OAuth2-protected endpoint.

Usage:
    from hangarllm.proxy_auth import AzureADCredential, ProxyAuthHandler

    hangarllm.proxy_auth = ProxyAuthHandler(
        credential=AzureADCredential(),
        scope="api://my-proxy/.default"
    )
"""

from .credentials import (
    AccessToken,
    AzureADCredential,
    GenericOAuth2Credential,
    ProxyAuthHandler,
    TokenCredential,
)

__all__ = [
    "AccessToken",
    "AzureADCredential",
    "GenericOAuth2Credential",
    "ProxyAuthHandler",
    "TokenCredential",
]
