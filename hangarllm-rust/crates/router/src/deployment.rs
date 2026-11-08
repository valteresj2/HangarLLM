use std::time::Duration;

use hangarllm_inference_messages::MessagesShaping;
use hangarllm_router_types::HangarllmParams;

#[derive(Clone, Debug, Default)]
pub struct Deployment {
    pub model: String,
    pub api_key: Option<String>,
    pub api_base: Option<String>,
    pub custom_llm_provider: Option<String>,
    pub hangarllm_params: HangarllmParams,
    pub timeout: Option<Duration>,
    pub shaping: MessagesShaping,
}
