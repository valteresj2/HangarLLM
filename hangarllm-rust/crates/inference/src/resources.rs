use std::sync::Arc;

use hangarllm_auth::AuthServices;
use hangarllm_http::HttpClientPool;

#[derive(Clone)]
pub struct CoreResources {
    pub pool: Arc<HttpClientPool>,
    pub auth: Arc<AuthServices>,
}

impl CoreResources {
    pub fn new(pool: Arc<HttpClientPool>) -> Self {
        Self {
            pool,
            auth: Arc::new(AuthServices::default()),
        }
    }
}
