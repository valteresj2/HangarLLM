import enum


class CommonProxyErrors(str, enum.Enum):
    db_not_connected_error = (
        "DB not connected. This endpoint needs a database; set DATABASE_URL to a "
        "PostgreSQL connection string (postgresql://...) to enable it."
    )
    no_llm_router = "No models configured on proxy"
    not_allowed_access = "Admin-only endpoint. Not allowed to access this."
    # HangarLLM is fully open source: this is only raised when an operator switched a
    # feature off with HANGARLLM_DISABLED_FEATURES.
    not_premium_user = (
        " is disabled on this HangarLLM deployment (HANGARLLM_DISABLED_FEATURES). "
        "Ask your administrator to re-enable it."
    )
    max_parallel_request_limit_reached = "Crossed TPM / RPM / Max Parallel Request Limit"
    missing_enterprise_package = (
        " is unavailable: the HangarLLM extensions module (hangarllm.hangar) failed to import. "
        "Reinstall HangarLLM or check the server logs."
    )
    missing_enterprise_package_docker = (
        " is unavailable: the HangarLLM extensions module (hangarllm.hangar) failed to import. "
        "Reinstall HangarLLM or check the server logs."
    )
