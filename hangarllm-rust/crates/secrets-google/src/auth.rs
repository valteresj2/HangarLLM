use std::sync::Arc;

use hangarllm_auth_gcp::{GoogleCredentials, VertexConfig};
use hangarllm_auth_types::{InputSource, Sourced};
use hangarllm_core_utils::settings::Lookup;
use hangarllm_secret_value::SecretValue;

pub(crate) fn credentials(
    project: Option<String>,
    credentials: Option<SecretValue>,
    environment: Arc<dyn Lookup + Send + Sync>,
) -> GoogleCredentials {
    GoogleCredentials::new(
        VertexConfig::new(
            credentials.map(|value| Sourced::new(value, InputSource::Environment)),
            project,
            None,
        ),
        Arc::new(move |name| environment.get(name)),
    )
}
