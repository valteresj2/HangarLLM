use std::convert::Infallible;

use bytes::Bytes;
use hangarllm_host::{
    call::{HostedCompletion, HostedMachine, hosted_call},
    protocol::Protocol,
};
use hangarllm_llms_types::formats::messages::MessagesResponse;

use super::{Error, MessagesCall};

pub type MessagesOutput = HostedCompletion<Box<MessagesResponse>>;

/// The upstream response as the caller sees it at stream hand-off, before any chunk.
pub struct MessagesStreamHead {
    pub headers: Vec<(String, String)>,
}

pub struct Messages;

impl Protocol for Messages {
    type Response = Box<MessagesResponse>;
    type Error = Error;
    type Request = MessagesCall;
    type HostCall = Infallible;
    type Chunk = Bytes;
    type StreamHead = MessagesStreamHead;
}

pub type MessagesMachine = HostedMachine<Messages>;

impl super::MessagesRoute {
    pub fn machine(
        self,
        request: super::MessagesCall,
        options: impl Into<hangarllm_inference::CallOptions>,
    ) -> MessagesMachine {
        let hangarllm_inference::CallOptions {
            cache: cache_options,
            observers,
        } = options.into();
        hosted_call(
            request,
            observers,
            move |call, _, interceptors, observers| async move {
                let context = hangarllm_inference::context::CallContext::new(
                    &interceptors,
                    hangarllm_inference::CallOptions {
                        cache: cache_options,
                        observers,
                    },
                );
                self.run(call, context).await
            },
        )
    }
}

impl hangarllm_inference::caching::Cachable for Messages {
    const SURFACE: &'static str = "messages";
}

impl hangarllm_inference::caching::StreamCachable for Messages {
    const TERMINAL_EVENT: &'static str = "message_stop";

    fn replay(data: bytes::Bytes) -> Option<hangarllm_host::call::OutputOf<Self>> {
        Some(hangarllm_host::call::CallOutput::Stream {
            head: MessagesStreamHead {
                headers: Vec::new(),
            },
            chunks: Box::pin(futures_util::stream::iter([Ok(data)])),
        })
    }

    fn bytes(chunk: &Self::Chunk) -> &[u8] {
        chunk.as_ref()
    }
}
