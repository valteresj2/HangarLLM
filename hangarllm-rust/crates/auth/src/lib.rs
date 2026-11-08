#![forbid(unsafe_code)]

pub use hangarllm_auth_types::*;

mod services;
pub use services::AuthServices;

#[cfg(feature = "aws")]
pub use hangarllm_auth_aws as aws;
#[cfg(feature = "azure")]
pub use hangarllm_auth_azure as azure;
#[cfg(feature = "gcp")]
pub use hangarllm_auth_gcp as gcp;
