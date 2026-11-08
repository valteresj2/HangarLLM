pub mod context;
pub mod diagnostic;

pub mod caching;
pub mod error;
pub mod outbound;
pub mod provider;
pub mod resources;

pub use error::Error;

#[derive(Clone, Default)]
pub struct CallOptions {
    pub cache: Option<hangarllm_cache_response::CachePolicy>,
    pub observers: Option<hangarllm_host::observation::ObservationSender>,
}

impl From<Option<hangarllm_host::observation::ObservationSender>> for CallOptions {
    fn from(observers: Option<hangarllm_host::observation::ObservationSender>) -> Self {
        Self {
            cache: None,
            observers,
        }
    }
}

impl From<hangarllm_cache_response::CachePolicy> for CallOptions {
    fn from(cache: hangarllm_cache_response::CachePolicy) -> Self {
        Self {
            cache: Some(cache),
            observers: None,
        }
    }
}
