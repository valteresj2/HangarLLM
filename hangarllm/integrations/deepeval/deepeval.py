import os
from typing import Final

from hangarllm._logging import verbose_logger
from hangarllm._uuid import uuid
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.integrations.deepeval.api import Api, Endpoints, HttpMethods
from hangarllm.integrations.deepeval.types import (
    BaseApiSpan,
    SpanApiType,
    TraceApi,
    TraceSpanApiStatus,
)
from hangarllm.integrations.deepeval.utils import (
    to_zod_compatible_iso,
    validate_environment,
)
from hangarllm.hangarllm_core_utils.internal_call_metadata import logged_event_key


# This file includes the custom callbacks for HangarLLM Proxy
# Once defined, these can be passed in proxy_config.yaml
class DeepEvalLogger(CustomLogger):
    """Logs hangarllm traces to DeepEval's platform."""

    def __init__(self, *args, **kwargs):
        api_key: Final = os.getenv("CONFIDENT_API_KEY")
        self.hangarllm_environment = os.getenv("LITELM_ENVIRONMENT", "development")
        validate_environment(self.hangarllm_environment)
        if not api_key:
            raise ValueError("Please set 'CONFIDENT_API_KEY=<>' in your environment variables.")
        self.api = Api(api_key=api_key)
        super().__init__(*args, **kwargs)

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Logs a success event to DeepEval's platform."""
        self._sync_event_handler(kwargs, response_obj, start_time, end_time, is_success=True)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        """Logs a failure event to DeepEval's platform."""
        self._sync_event_handler(kwargs, response_obj, start_time, end_time, is_success=False)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        """Logs a failure event to DeepEval's platform."""
        await self._async_event_handler(kwargs, response_obj, start_time, end_time, is_success=False)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Logs a success event to DeepEval's platform."""
        await self._async_event_handler(kwargs, response_obj, start_time, end_time, is_success=True)

    def _prepare_trace_api(self, kwargs, response_obj, start_time, end_time, is_success):
        _start_time: Final = to_zod_compatible_iso(start_time)
        _end_time: Final = to_zod_compatible_iso(end_time)
        _standard_logging_object: Final = kwargs.get("standard_logging_object", {})
        base_api_span: Final = self._create_base_api_span(
            kwargs,
            standard_logging_object=_standard_logging_object,
            start_time=_start_time,
            end_time=_end_time,
            is_success=is_success,
        )
        trace_api: Final = self._create_trace_api(
            base_api_span,
            standard_logging_object=_standard_logging_object,
            start_time=_start_time,
            end_time=_end_time,
            hangarllm_environment=self.hangarllm_environment,
        )

        body = {}

        try:
            body = trace_api.model_dump(by_alias=True, exclude_none=True)
        except AttributeError:
            # Pydantic version below 2.0
            body = trace_api.dict(by_alias=True, exclude_none=True)
        return body

    def _sync_event_handler(self, kwargs, response_obj, start_time, end_time, is_success):
        body: Final = self._prepare_trace_api(kwargs, response_obj, start_time, end_time, is_success)
        try:
            response: Final = self.api.send_request(
                method=HttpMethods.POST,
                endpoint=Endpoints.TRACING_ENDPOINT,
                body=body,
            )
        except Exception as e:
            raise e
        verbose_logger.debug("DeepEvalLogger: sync_log_failure_event: Api response %s", response)

    async def _async_event_handler(self, kwargs, response_obj, start_time, end_time, is_success):
        body: Final = self._prepare_trace_api(kwargs, response_obj, start_time, end_time, is_success)
        response: Final = await self.api.a_send_request(
            method=HttpMethods.POST,
            endpoint=Endpoints.TRACING_ENDPOINT,
            body=body,
        )

        verbose_logger.debug("DeepEvalLogger: async_event_handler: Api response %s", response)

    def _create_base_api_span(self, kwargs, standard_logging_object, start_time, end_time, is_success):
        # extract usage
        usage: Final = standard_logging_object.get("response", {}).get("usage", {})
        if is_success:
            output = (
                standard_logging_object.get("response", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "NO_OUTPUT")
            )
        else:
            output = str(standard_logging_object.get("error_string", ""))
        logged_id: Final = standard_logging_object.get("id", uuid.uuid4())
        span_id: Final = logged_event_key(kwargs, logged_id) if isinstance(logged_id, str) else logged_id
        return BaseApiSpan(
            uuid=span_id,
            name=("hangarllm_success_callback" if is_success else "hangarllm_failure_callback"),
            status=(TraceSpanApiStatus.SUCCESS if is_success else TraceSpanApiStatus.ERRORED),
            type=SpanApiType.LLM,
            traceUuid=standard_logging_object.get("trace_id", uuid.uuid4()),
            startTime=str(start_time),
            endTime=str(end_time),
            input=kwargs.get("input", "NO_INPUT"),
            output=output,
            model=standard_logging_object.get("model", None),
            inputTokenCount=usage.get("prompt_tokens", None) if is_success else None,
            outputTokenCount=(usage.get("completion_tokens", None) if is_success else None),
        )

    def _create_trace_api(
        self,
        base_api_span,
        standard_logging_object,
        start_time,
        end_time,
        hangarllm_environment,
    ):
        return TraceApi(
            uuid=standard_logging_object.get("trace_id", uuid.uuid4()),
            baseSpans=[],
            agentSpans=[],
            llmSpans=[base_api_span],
            retrieverSpans=[],
            toolSpans=[],
            startTime=str(start_time),
            endTime=str(end_time),
            environment=hangarllm_environment,
        )
