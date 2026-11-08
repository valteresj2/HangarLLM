from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from hangarllm.llms.base_llm.chat.transformation import BaseConfig
from hangarllm.types.llms.openai import AllMessageValues, OpenAITextCompletionUserMessage
from hangarllm.types.utils import ModelResponse

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj
    from hangarllm.hangarllm_core_utils.tokenizer import Encoding as Tokenizer

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any


class BaseTextCompletionConfig(BaseConfig, ABC):
    @abstractmethod
    def transform_text_completion_request(
        self,
        model: str,
        messages: list[AllMessageValues] | list[OpenAITextCompletionUserMessage],
        optional_params: dict,
        headers: dict,
    ) -> dict:
        return {}

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict,
        hangarllm_params: dict,
        stream: bool | None = None,
    ) -> str:
        """
        OPTIONAL

        Get the complete url for the request

        Some providers need `model` in `api_base`
        """
        return api_base or ""

    def transform_request(
        self,
        model: str,
        messages: list[AllMessageValues],
        optional_params: dict,
        hangarllm_params: dict,
        headers: dict,
    ) -> dict:
        raise NotImplementedError(
            "AudioTranscriptionConfig does not need a request transformation for audio transcription models"
        )

    def transform_response(
        self,
        model: str,
        raw_response: httpx.Response,
        model_response: ModelResponse,
        logging_obj: HangarLLMLoggingObj,
        request_data: dict,
        messages: list[AllMessageValues],
        optional_params: dict,
        hangarllm_params: dict,
        encoding: "Tokenizer | None",
        api_key: str | None = None,
        json_mode: bool | None = None,
    ) -> ModelResponse:
        raise NotImplementedError(
            "AudioTranscriptionConfig does not need a response transformation for audio transcription models"
        )
