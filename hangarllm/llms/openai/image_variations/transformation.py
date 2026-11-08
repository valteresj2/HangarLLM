from typing import TYPE_CHECKING

from aiohttp import ClientResponse
from httpx import Headers, Response

from hangarllm.llms.base_llm.chat.transformation import BaseLLMException
from hangarllm.llms.base_llm.image_variations.transformation import HangarLLMLoggingObj
from hangarllm.types.llms.openai import OpenAIImageVariationOptionalParams
from hangarllm.types.utils import FileTypes, HttpHandlerRequestFields, ImageResponse

from ...base_llm.image_variations.transformation import BaseImageVariationConfig
from ..common_utils import OpenAIError

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.tokenizer import Encoding as Tokenizer


class OpenAIImageVariationConfig(BaseImageVariationConfig):
    def get_supported_openai_params(self, model: str) -> list[OpenAIImageVariationOptionalParams]:
        return ["n", "size", "response_format", "user"]

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        optional_params.update(non_default_params)
        return optional_params

    def transform_request_image_variation(
        self,
        model: str | None,
        image: FileTypes,
        optional_params: dict,
        headers: dict,
    ) -> HttpHandlerRequestFields:
        return {
            "data": {
                "image": image,
                **optional_params,
            }
        }

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
        return model_response

    def transform_response_image_variation(
        self,
        model: str | None,
        raw_response: Response,
        model_response: ImageResponse,
        logging_obj: HangarLLMLoggingObj,
        request_data: dict,
        image: FileTypes,
        optional_params: dict,
        hangarllm_params: dict,
        encoding: "Tokenizer | None",
        api_key: str | None = None,
    ) -> ImageResponse:
        return model_response

    def get_error_class(self, error_message: str, status_code: int, headers: dict | Headers) -> BaseLLMException:
        return OpenAIError(
            status_code=status_code,
            message=error_message,
            headers=headers,
        )
