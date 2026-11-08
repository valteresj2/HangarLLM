#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error(transparent)]
    Http(#[from] hangarllm_http::Error),
    #[error("environment_variables values must be strings, numbers or booleans")]
    Environment,
    #[error("MCP host does not yet support configured setting {0}")]
    McpSetting(String),
    #[error("MCP host does not yet support guardrails or policies")]
    McpGuardrails,
    #[error(transparent)]
    Mcp(#[from] hangarllm_gateway_mcp::ConnectError),
    #[error(transparent)]
    Config(#[from] hangarllm_config::Error),
    #[error(transparent)]
    Redis(#[from] hangarllm_redis_resolve::Error),
    #[error("Redis setting {setting} is not plain data")]
    RedisNotPlainData { setting: String },
    #[error(transparent)]
    RedisConnect(#[from] hangarllm_redis_connect::Error),
    #[error("MCP requires working gateway authentication")]
    Auth(#[from] hangarllm_gateway_auth::Error),
}
