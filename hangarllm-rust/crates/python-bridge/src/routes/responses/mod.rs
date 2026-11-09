mod host;
mod websocket;

use std::sync::Arc;

use hangarllm_auth::AuthServices;
use hangarllm_cache_response::CachePolicy;
use hangarllm_callbacks_legacy_python::LoggingOperation;
use hangarllm_host::{call::HostedMachine, protocol::Protocol};
use hangarllm_inference_responses::{ResponsesRoute, route::Responses};
use hangarllm_secrets::source::SecretSource;
use host::ResponsesPythonHost;
use pyo3::prelude::*;
pub(crate) use websocket::ResponsesWebSocketConnection;

use super::{
    NativeCall,
    inference::{InferenceHost, InferenceRoute, run_inference},
};

const ROUTE_HOST_MODULE: &str = "hangarllm.rust_bridge.host.routes.responses";

fn run_responses(py: Python<'_>, call: NativeCall<'_>, asynchronous: bool) -> PyResult<Py<PyAny>> {
    let host = InferenceHost::new(call.view()?, ROUTE_HOST_MODULE);
    run_inference::<ResponsesRoute, _>(py, call, asynchronous, ResponsesPythonHost::new(host))
}

#[pyfunction]
pub(crate) fn responses(py: Python<'_>, call: NativeCall<'_>) -> PyResult<Py<PyAny>> {
    run_responses(py, call, false)
}

#[pyfunction]
pub(crate) fn aresponses(py: Python<'_>, call: NativeCall<'_>) -> PyResult<Py<PyAny>> {
    run_responses(py, call, true)
}

impl InferenceRoute for ResponsesRoute {
    type Protocol = Responses;
    const OPERATION: LoggingOperation = LoggingOperation::Responses;
    const SYNC_CALL_TYPE: &'static str = "responses";
    const ASYNC_CALL_TYPE: &'static str = "aresponses";

    fn new(
        http: hangarllm_http::Client,
        auth: Arc<AuthServices>,
        secrets: Arc<dyn SecretSource>,
    ) -> Self {
        Self::new(http, auth, secrets)
    }

    fn machine(
        self,
        call: <Responses as Protocol>::Request,
        policy: CachePolicy,
    ) -> HostedMachine<Responses> {
        self.machine(call, policy)
    }
}
