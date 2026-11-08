"""
Transformation for Bedrock Mantle (Claude Mythos Preview) - /messages endpoint

Inherits all Messages API request/response transformations from
AmazonAnthropicClaudeMessagesConfig. Overrides the URL, the model-prefix
stripping, and the anthropic-version / anthropic-beta placement (headers,
never the body) that are specific to the bedrock-mantle endpoint.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import httpx
from pydantic import TypeAdapter

from hangarllm.llms.anthropic.messages.native.transformation import (
    DEFAULT_ANTHROPIC_API_VERSION,
    AnthropicMessagesConfig,
)
from hangarllm.llms.bedrock.common_utils import build_mantle_messages_url
from hangarllm.llms.bedrock.messages.invoke_transformations.anthropic_claude_transformation import (
    AmazonAnthropicClaudeMessagesConfig,
)
from hangarllm.types.llms.anthropic_messages.anthropic_response import (
    AnthropicMessagesResponse,
    AnthropicUsage,
)
from hangarllm.types.router import GenericHangarLLMParams

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any

_BODY_FIELDS_MANTLE_READS_FROM_HEADERS: Final = frozenset({"anthropic_version", "anthropic_beta"})
_ANTHROPIC_BETAS: Final = TypeAdapter(tuple[str, ...])
_MANTLE_REQUEST: Final = TypeAdapter(dict[str, object])


def _move_betas_into_header(request: Mapping[str, object], headers: dict[str, str]) -> None:
    betas: Final = _ANTHROPIC_BETAS.validate_python(request.get("anthropic_beta") or ())
    if betas:
        headers["anthropic-beta"] = ",".join(betas)  # rebind-ok: the handler signs and sends this same dict
        return
    headers.pop("anthropic-beta", None)


class AmazonMantleMessagesConfig(AmazonAnthropicClaudeMessagesConfig):
    """
    Config for the bedrock-mantle /messages endpoint (Claude Mythos Preview).

    The mantle endpoint uses the Anthropic Messages API format and requires the
    model ID in the request body (unlike Bedrock Invoke which puts it in the URL).
    """

    BEDROCK_INVOKE_ALLOWED_TOP_LEVEL_FIELDS = (
        AmazonAnthropicClaudeMessagesConfig.BEDROCK_INVOKE_ALLOWED_TOP_LEVEL_FIELDS | {"service_tier"}
    )

    @property
    def beta_headers_provider(self) -> str:
        return "bedrock_mantle"

    def should_filter_anthropic_beta_headers(self) -> bool:
        return False

    def drops_dangerous_tool_use_beta_without_safeguards(self) -> bool:
        return False

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict,
        hangarllm_params: dict,
        stream: bool | None = None,
    ) -> str:
        region: Final = self._get_aws_region_name(optional_params=optional_params, model=model)
        return build_mantle_messages_url(
            api_base=api_base,
            aws_bedrock_runtime_endpoint=optional_params.get("aws_bedrock_runtime_endpoint"),
            region=region,
        )

    def validate_anthropic_messages_environment(
        self,
        headers: dict,
        model: str,
        messages: Sequence[object],
        optional_params: dict,
        hangarllm_params: dict,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> tuple[dict, str | None]:
        merged_headers, resolved_api_base = super().validate_anthropic_messages_environment(
            headers=headers,
            model=model,
            messages=messages,
            optional_params=optional_params,
            hangarllm_params=hangarllm_params,
            api_key=api_key,
            api_base=api_base,
        )
        project_id: Final = hangarllm_params.get("aws_bedrock_project_id")
        has_version: Final = any(name.lower() == "anthropic-version" for name in merged_headers)
        mantle_headers: Final = MappingProxyType(
            {
                name: value
                for name, value in (
                    ("anthropic-workspace-id", project_id),
                    ("anthropic-version", None if has_version else DEFAULT_ANTHROPIC_API_VERSION),
                )
                if value
            }
        )
        return {
            **merged_headers,
            **mantle_headers,
        }, resolved_api_base

    def transform_anthropic_messages_request(
        self,
        model: str,
        messages: list[dict],
        anthropic_messages_optional_request_params: dict,
        hangarllm_params: GenericHangarLLMParams,
        headers: dict,
    ) -> dict:
        model_id: Final = model.replace("mantle/", "", 1)
        request: Final = _MANTLE_REQUEST.validate_python(
            super().transform_anthropic_messages_request(
                model=model_id,
                messages=messages,
                anthropic_messages_optional_request_params=anthropic_messages_optional_request_params,
                hangarllm_params=hangarllm_params,
                headers=headers,
            ),
        )
        _move_betas_into_header(request, headers)
        body: Final = MappingProxyType(
            {key: value for key, value in request.items() if key not in _BODY_FIELDS_MANTLE_READS_FROM_HEADERS}
        )
        streaming: Final = anthropic_messages_optional_request_params.get("stream") is True
        mantle_fields: Final = MappingProxyType(
            {key: value for key, value in (("model", model_id), ("stream", streaming)) if value}
        )
        return {
            **body,
            **mantle_fields,
        }

    def transform_anthropic_messages_response(
        self,
        model: str,
        raw_response: httpx.Response,
        logging_obj: HangarLLMLoggingObj,
    ) -> AnthropicMessagesResponse:
        response: Final = super().transform_anthropic_messages_response(
            model=model,
            raw_response=raw_response,
            logging_obj=logging_obj,
        )
        existing_usage: Final[AnthropicUsage] = response.get("usage") or AnthropicUsage()
        normalized_usage: Final[AnthropicUsage] = {
            "input_tokens": 0,
            "output_tokens": 0,
            **existing_usage,
        }
        return {**response, "usage": normalized_usage}

    def get_async_streaming_response_iterator(
        self,
        model: str,
        httpx_response: httpx.Response,
        request_body: dict[str, object],  # mutable-ok: mirrors the base signature
        hangarllm_logging_obj: HangarLLMLoggingObj,
    ) -> AsyncIterator[bytes]:
        return AnthropicMessagesConfig.get_async_streaming_response_iterator(
            self,
            model=model,
            httpx_response=httpx_response,
            request_body=request_body,
            hangarllm_logging_obj=hangarllm_logging_obj,
        )
