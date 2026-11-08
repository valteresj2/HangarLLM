use hangarllm_host::observation::ObservationSender;
pub mod route;
pub mod types;
pub use hangarllm_inference::Error;
mod common_utils;
pub mod constants;
pub(crate) mod handler;
use hangarllm_llms_types::formats::chat_completions::ChatCompletionsResponse;

use hangarllm_auth::AuthServices;
use hangarllm_inference::provider::resolve_llm_provider;
use hangarllm_secrets::source::SecretSource;
use std::sync::Arc;
use types::{ChatCompletionsCall, ChatCompletionsRequest};

#[derive(Clone)]
pub struct ChatCompletionsRoute {
    http: hangarllm_http::Client,
    auth: Arc<AuthServices>,
    secrets: Arc<dyn SecretSource>,
    cache: Option<hangarllm_cache_response::ScopedCache>,
}

impl ChatCompletionsRoute {
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
        request: ChatCompletionsRequest<'_>,
        interceptors: &impl hangarllm_host::interceptors::Interceptors<Error>,
        options: impl Into<hangarllm_inference::CallOptions>,
    ) -> Result<ChatCompletionsResponse, Error> {
        let hangarllm_inference::CallOptions {
            cache: cache_options,
            observers,
        } = options.into();
        hangarllm_host::lifecycle::observe_unary(
            observers.clone(),
            self.run(
                request.into(),
                cache_options,
                interceptors,
                observers.as_ref(),
            ),
        )
        .await
    }

    #[tracing::instrument(name = "hangarllm.route", skip_all, fields(
        route = "chat_completions",
        model = %call.model,
        provider,
        resolved_model,
        stream = false,
        outcome
    ))]
    async fn run(
        &self,
        call: ChatCompletionsCall,
        cache_options: Option<hangarllm_cache_response::CachePolicy>,
        interceptors: &impl hangarllm_host::interceptors::Interceptors<Error>,
        observers: Option<&ObservationSender>,
    ) -> Result<ChatCompletionsResponse, Error> {
        hangarllm_inference::diagnostic::unary(async {
            let model = call.model.clone();
            let custom_llm_provider = call.custom_llm_provider.clone();
            let provider =
                resolve_llm_provider(&model, custom_llm_provider.as_deref(), "chat completions")?;
            let config = common_utils::chat_completions_provider(provider.provider)
                .ok_or_else(|| Error::InvalidProvider(<&str>::from(provider.provider).to_string()))?
                .config();
            let call = common_utils::resolve_request(call, config)?;
            hangarllm_inference::diagnostic::provider(
                provider.model,
                <&'static str>::from(provider.provider),
            );
            let secrets = self.secrets.resolve(&config.secret_names()).await?;
            let execute: futures_util::future::BoxFuture<
                '_,
                Result<ChatCompletionsResponse, Error>,
            > = Box::pin(handler::execute(
                &self.http,
                &self.auth,
                config,
                provider,
                call,
                secrets,
                self.cache.clone(),
                cache_options,
                interceptors,
                observers,
            ));
            execute.await
        })
        .await
    }
}
