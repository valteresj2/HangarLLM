use hangarllm_host::observation::ObservationSender;
pub use hangarllm_inference::Error;

pub mod ids;
pub mod route;
pub mod types;
pub mod websocket;

mod handler;

use std::sync::Arc;

use hangarllm_auth::AuthServices;
use hangarllm_core_utils::decline::Decline;
use hangarllm_core_utils::get_llm_provider_logic::{
    CustomLlmProvider, LlmProviders, get_custom_llm_provider,
};
use hangarllm_host::interceptors::Interceptors;
use hangarllm_host::interceptors::ProviderIdentity;
use hangarllm_llms::{
    base_llm::responses::transformation::BaseResponsesApiConfig,
    openai::responses::transformation::OpenAiResponsesApiConfig,
    openrouter::responses::transformation::OPENROUTER_RESPONSES_CONFIG,
};
use hangarllm_secrets::source::SecretSource;
use types::{ResponsesCall, ResponsesOutput, ResponsesProvider};

const NOT_NATIVE: Decline = Decline::new("native HTTP responses provider");

fn responses_provider(provider: LlmProviders) -> Option<&'static dyn BaseResponsesApiConfig> {
    match provider {
        LlmProviders::Openai => Some(&OpenAiResponsesApiConfig),
        LlmProviders::Openrouter => Some(&OPENROUTER_RESPONSES_CONFIG),
        _ => None,
    }
}

#[derive(Clone)]
pub struct ResponsesRoute {
    http: hangarllm_http::Client,
    auth: Arc<AuthServices>,
    secrets: Arc<dyn SecretSource>,
    cache: Option<hangarllm_cache_response::ScopedCache>,
}

impl ResponsesRoute {
    pub fn new(
        http: hangarllm_http::Client,
        auth: Arc<AuthServices>,
        secrets: Arc<dyn SecretSource>,
    ) -> Self {
        Self {
            http,
            auth,
            secrets,
            cache: None,
        }
    }

    pub fn with_cache(self, cache: hangarllm_cache_response::ScopedCache) -> Self {
        Self {
            cache: Some(cache),
            ..self
        }
    }

    pub async fn execute(
        &self,
        call: ResponsesCall,
        interceptors: &impl Interceptors<Error>,
        options: impl Into<hangarllm_inference::CallOptions>,
    ) -> Result<ResponsesOutput, Error> {
        let hangarllm_inference::CallOptions {
            cache: cache_options,
            observers,
        } = options.into();
        hangarllm_host::lifecycle::observe_call(
            observers.clone(),
            self.run(call, cache_options, interceptors, observers.as_ref()),
        )
        .await
    }

    #[tracing::instrument(name = "hangarllm.route", skip_all, fields(
        route = "responses",
        model = %call.model,
        provider,
        resolved_model,
        stream = call.optional_params.get("stream").and_then(serde_json::Value::as_bool).unwrap_or(false),
        outcome
    ))]
    async fn run(
        &self,
        call: ResponsesCall,
        cache_options: Option<hangarllm_cache_response::CachePolicy>,
        interceptors: &impl hangarllm_host::interceptors::Interceptors<Error>,
        observers: Option<&ObservationSender>,
    ) -> Result<ResponsesOutput, Error> {
        hangarllm_inference::diagnostic::call(async {
            let explicit = call
                .custom_llm_provider
                .as_deref()
                .filter(|provider| !provider.is_empty());
            let (provider_name, resolved_model) =
                match get_custom_llm_provider(&call.model, explicit) {
                    Some(CustomLlmProvider {
                        model,
                        custom_llm_provider,
                    }) => (custom_llm_provider, model),
                    None => ("openai", call.model.as_str()),
                };
            if resolved_model.is_empty() {
                return Err(Error::InvalidProvider(call.model));
            }
            let provider = provider_name
                .parse::<LlmProviders>()
                .map_err(|_| Error::Declined(NOT_NATIVE))?;
            let config = responses_provider(provider).ok_or(Error::Declined(NOT_NATIVE))?;
            let wire_model = match provider {
                LlmProviders::Openai if resolved_model.contains('/') => {
                    return Err(Error::InvalidProvider(call.model));
                }
                LlmProviders::Openai => resolved_model.into(),
                LlmProviders::Openrouter if explicit.is_some() && !resolved_model.contains('/') => {
                    format!("openrouter/{resolved_model}")
                }
                LlmProviders::Openrouter => resolved_model.into(),
                _ => return Err(Error::Declined(NOT_NATIVE)),
            };
            let provider = ResponsesProvider {
                identity: ProviderIdentity {
                    model: wire_model,
                    provider: provider_name.into(),
                },
                config,
            };
            hangarllm_inference::diagnostic::provider(
                &provider.identity.model,
                &provider.identity.provider,
            );
            let secrets = self
                .secrets
                .resolve(
                    provider
                        .config
                        .secret_names(call.api_key.as_deref(), call.api_base.as_deref()),
                )
                .await?;
            let execute: futures_util::future::BoxFuture<'_, Result<ResponsesOutput, Error>> =
                Box::pin(handler::execute(
                    self,
                    provider,
                    call,
                    secrets,
                    cache_options,
                    interceptors,
                    observers,
                ));
            execute.await
        })
        .await
    }
}
