from pydantic import Field

from hangarllm.types.llms.base import HangarLLMBaseModel
from hangarllm.types.proxy.control_plane_endpoints import WorkerRegistryEntry


class UiDiscoveryEndpoints(HangarLLMBaseModel):
    server_root_path: str
    proxy_base_url: str | None
    gateway_base_url: str | None = None
    auto_redirect_to_sso: bool
    admin_ui_disabled: bool
    sso_configured: bool
    hide_default_credentials_hint: bool = False
    is_control_plane: bool = False
    mcp_stdio_enabled: bool = False
    use_si_terminology: bool = False
    claude_code_marketplace_auth_required: bool = False
    workers: list[WorkerRegistryEntry] = Field(default=[])
