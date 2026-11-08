use std::time::Duration;

use bytes::Bytes;
use hangarllm_host::call::CallOutput;
use hangarllm_host::interceptors::ProviderIdentity;
use hangarllm_llms::base_llm::responses::transformation::BaseResponsesApiConfig;
use hangarllm_llms_types::formats::responses::ResponsesApiResponse;
use serde_json::{Map, Value};

use super::Error;

pub struct ResponsesCall {
    pub model: String,
    pub input: Value,
    pub optional_params: Map<String, Value>,
    pub api_key: Option<String>,
    pub api_base: Option<String>,
    pub custom_llm_provider: Option<String>,
    pub extra_headers: Option<Map<String, Value>>,
    pub timeout: Option<Duration>,
}

pub(crate) struct ResponsesProvider {
    pub identity: ProviderIdentity,
    pub config: &'static dyn BaseResponsesApiConfig,
}

pub struct ResponsesStreamHead {
    pub headers: Vec<(String, String)>,
}

pub type ResponsesOutput = CallOutput<ResponsesApiResponse, ResponsesStreamHead, Bytes, Error>;
