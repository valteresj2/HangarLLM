from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx
from aiohttp import ClientResponse

from hangarllm.llms.base_llm.chat.transformation import BaseConfig
from hangarllm.types.llms.openai import (
    AllMessageValues,
    OpenAIImageVariationOptionalParams,
)
from hangarllm.types.utils import (
    FileTypes,
    HttpHandlerRequestFields,
    ImageResponse,
    ModelResponse,
)

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj
    from hangarllm.hangarllm_core_utils.tokenizer import Encoding as Tokenizer

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any


class BaseImageVariationConfig(BaseConfig, ABC):
    @abstractmethod
    def get_supported_openai_params(self, model: str) -> list[OpenAIImageVariationOptionalParams]:
        pass

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

    @abstractmethod
    def transform_request_image_variation(
        self,
        model: str | None,
        image: FileTypes,
        optional_params: dict,
        headers: dict,
    ) -> HttpHandlerRequestFields:
        pass

    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages: list[AllMessageValues],
        optional_params: dict,
        hangarllm_params: dict,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict:
        return {}

    @abstractmethod
    async def async_transform_response_image_variation(
        self,
        model: str | None,
        raw_response: ClientResponse,
        model_response: ImageResponse,
        logging_obj: HangarLLMLoggingObj,
        request_data: dict,
        image: FileTypes,
        optional_params: dict,
        hangarllm_params: dict,
        encoding: "Tokenizer | None",
        api_key: str | None = None,
    ) -> ImageResponse:
        pass

    @abstractmethod
    def transform_response_image_variation(
        self,
        model: str | None,
        raw_response: httpx.Response,
        model_response: ImageResponse,
        logging_obj: HangarLLMLoggingObj,
        request_data: dict,
        image: FileTypes,
        optional_params: dict,
        hangarllm_params: dict,
        encoding: "Tokenizer | None",
        api_key: str | None = None,
    ) -> ImageResponse:
        pass

    def transform_request(
        self,
        model: str,
        messages: list[AllMessageValues],
        optional_params: dict,
        hangarllm_params: dict,
        headers: dict,
    ) -> dict:
        raise NotImplementedError(
            "ImageVariationConfig implementa 'transform_request_image_variation' for image variation models"
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
            "ImageVariationConfig implements 'transform_response_image_variation' for image variation models"
        )
