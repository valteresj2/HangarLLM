from collections.abc import Mapping
from typing import Any, Final

from hangarllm.exceptions import AuthenticationError
from hangarllm.llms.openai.openai import OpenAIConfig
from hangarllm.types.llms.openai import AllMessageValues
from hangarllm.types.router import GenericHangarLLMParams

from ..authenticator import Authenticator, get_chatgpt_auth_file, resolve_chatgpt_authenticator
from ..common_utils import (
    GetAccessTokenError,
    chatgpt_client_api_base,
    ensure_chatgpt_session_id,
    get_chatgpt_client_credential,
    get_chatgpt_default_headers,
    get_chatgpt_request_credential,
    strip_chatgpt_client_credential_headers,
)
from .streaming_utils import ChatGPTToolCallNormalizer


class ChatGPTConfig(OpenAIConfig):
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        custom_llm_provider: str = "openai",
        authenticator: Authenticator | None = None,
    ) -> None:
        super().__init__()
        self.authenticator = authenticator if authenticator is not None else Authenticator()

    @staticmethod
    def _get_access_token_or_raise(authenticator: Authenticator, model: str, llm_provider: str) -> str:
        try:
            return authenticator.get_access_token()
        except GetAccessTokenError as e:
            raise AuthenticationError(
                model=model,
                llm_provider=llm_provider,
                message=str(e),
            )

    def api_base_without_login(self) -> str:
        return self.authenticator.get_api_base()

    def _get_openai_compatible_provider_info(
        self,
        model: str,
        api_base: str | None,
        api_key: str | None,
        custom_llm_provider: str,
        hangarllm_params: Mapping[str, object] | GenericHangarLLMParams | None = None,
    ) -> tuple[str | None, str | None, str]:
        client_credential: Final = get_chatgpt_request_credential(hangarllm_params)
        if client_credential is not None:
            return chatgpt_client_api_base(api_base), client_credential.access_token, custom_llm_provider
        if api_key:
            return api_base or self.api_base_without_login(), api_key, custom_llm_provider
        authenticator: Final = resolve_chatgpt_authenticator(hangarllm_params, self.authenticator)
        dynamic_api_base: Final = authenticator.get_api_base()
        dynamic_api_key: Final = self._get_access_token_or_raise(authenticator, model, custom_llm_provider)
        return dynamic_api_base, dynamic_api_key, custom_llm_provider

    def get_openai_compatible_provider_info(
        self,
        model: str,
        api_base: str | None,
        api_key: str | None,
        custom_llm_provider: str,
        hangarllm_params: Mapping[str, object] | GenericHangarLLMParams | None = None,
    ) -> tuple[str | None, str | None, str]:
        return self._get_openai_compatible_provider_info(model, api_base, api_key, custom_llm_provider, hangarllm_params)

    def validate_environment(
        self,
        headers: dict[str, str],
        model: str,
        messages: list[AllMessageValues],
        optional_params: dict,
        hangarllm_params: dict[str, object],
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict[str, str]:
        client_credential: Final = get_chatgpt_client_credential(headers)
        if client_credential is not None:
            return dict(
                get_chatgpt_default_headers(
                    client_credential.access_token,
                    client_credential.account_id,
                    ensure_chatgpt_session_id(hangarllm_params),
                ),
                **strip_chatgpt_client_credential_headers(headers),
            )
        authenticator: Final = resolve_chatgpt_authenticator(hangarllm_params, self.authenticator)
        resolved_api_key: Final = (
            self._get_access_token_or_raise(authenticator, model, "chatgpt")
            if get_chatgpt_auth_file(hangarllm_params)
            else api_key
        )
        validated_headers: Final = super().validate_environment(
            dict(strip_chatgpt_client_credential_headers(headers)),
            model,
            messages,
            optional_params,
            hangarllm_params,
            resolved_api_key,
            api_base,
        )

        account_id: Final = authenticator.get_account_id(resolved_api_key)
        session_id: Final = ensure_chatgpt_session_id(hangarllm_params)
        default_headers: Final = get_chatgpt_default_headers(resolved_api_key or "", account_id, session_id)
        return {**default_headers, **validated_headers}

    def post_stream_processing(self, stream: Any) -> ChatGPTToolCallNormalizer:
        return ChatGPTToolCallNormalizer(stream)

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        optional_params = super().map_openai_params(non_default_params, optional_params, model, drop_params)
        optional_params.setdefault("stream", False)
        return optional_params
