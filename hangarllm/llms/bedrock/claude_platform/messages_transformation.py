from typing import Final

import hangarllm
from hangarllm.llms.anthropic.messages.native.transformation import (
    DEFAULT_ANTHROPIC_API_VERSION,
    AnthropicMessagesConfig,
)
from hangarllm.llms.bedrock.base_aws_llm import run_aws_signing
from hangarllm.secret_managers.main import get_secret_str
from hangarllm.types.router import GenericHangarLLMParams

from .common_utils import (
    BedrockClaudePlatformMixin,
    filter_claude_platform_request_body,
    resolve_unsupported_override,
    strip_claude_platform_route,
)


class BedrockClaudePlatformMessagesConfig(BedrockClaudePlatformMixin, AnthropicMessagesConfig):
    def should_filter_anthropic_beta_headers(self) -> bool:
        return False

    def validate_anthropic_messages_environment(
        self,
        headers: dict[str, str],  # mutable-ok: overrides the base signature
        model: str,
        messages: list[object],  # mutable-ok: overrides the base signature
        optional_params: dict[str, object],  # mutable-ok: overrides the base signature
        hangarllm_params: dict[str, object],  # mutable-ok: overrides the base signature
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> tuple[dict[str, str], str | None]:  # mutable-ok: overrides the base signature
        workspace_id: Final = self._get_workspace_id(optional_params, hangarllm_params)
        if workspace_id is None:
            raise hangarllm.AuthenticationError(
                message=(
                    "Missing workspace ID for Claude Platform on AWS. Pass "
                    "`workspace_id` or configure the provider workspace setting."
                ),
                llm_provider="bedrock",
                model=model,
            )

        resolved_api_key: Final = api_key or get_secret_str("ANTHROPIC_AWS_API_KEY")
        headers = {
            **headers,
            "anthropic-version": headers.get("anthropic-version", DEFAULT_ANTHROPIC_API_VERSION),
            "content-type": headers.get("content-type", "application/json"),
            "anthropic-workspace-id": workspace_id,
        }
        if resolved_api_key and "x-api-key" not in headers:
            headers["x-api-key"] = resolved_api_key

        return (
            self._update_headers_with_anthropic_beta(
                headers=headers,
                optional_params=filter_claude_platform_request_body(
                    optional_params,
                    unsupported_override=resolve_unsupported_override(
                        hangarllm_params, optional_params=optional_params, log_invalid=False
                    ),
                    log_dropped=False,
                ),
                messages=messages,
            ),
            api_base,
        )

    async def avalidate_anthropic_messages_environment(
        self,
        headers: dict[str, str],  # mutable-ok: mirrors validate_anthropic_messages_environment
        model: str,
        messages: list[object],  # mutable-ok: mirrors validate_anthropic_messages_environment
        optional_params: dict[str, object],  # mutable-ok: mirrors validate_anthropic_messages_environment
        hangarllm_params: dict[str, object],  # mutable-ok: mirrors validate_anthropic_messages_environment
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> tuple[dict[str, str], str | None]:  # mutable-ok: mirrors validate_anthropic_messages_environment
        return await run_aws_signing(
            self.validate_anthropic_messages_environment,
            headers=headers,
            model=model,
            messages=messages,
            optional_params=optional_params,
            hangarllm_params=hangarllm_params,
            api_key=api_key,
            api_base=api_base,
        )

    def transform_anthropic_messages_request(
        self,
        model: str,
        messages: list[dict[str, object]],
        anthropic_messages_optional_request_params: dict[str, object],
        hangarllm_params: GenericHangarLLMParams,
        headers: dict[str, str],
    ) -> dict[str, object]:
        return super().transform_anthropic_messages_request(
            model=strip_claude_platform_route(model),
            messages=messages,
            anthropic_messages_optional_request_params=filter_claude_platform_request_body(
                anthropic_messages_optional_request_params,
                unsupported_override=resolve_unsupported_override(
                    hangarllm_params, optional_params=anthropic_messages_optional_request_params
                ),
            ),
            hangarllm_params=hangarllm_params,
            headers=headers,
        )
