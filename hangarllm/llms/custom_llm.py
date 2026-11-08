# What is this?
## Handler file for a Custom Chat LLM

"""
- completion
- acompletion
- streaming
- async_streaming
"""

from collections.abc import AsyncIterator, Callable, Coroutine, Iterator, Sequence
from typing import (
    TYPE_CHECKING,
    Union,
)

import httpx
from openai.types.audio.transcription_create_params import FileTypes

from hangarllm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from hangarllm.types.utils import GenericStreamingChunk
from hangarllm.utils import EmbeddingResponse, ImageResponse, ModelResponse

from .base import BaseLLM

if TYPE_CHECKING:
    from hangarllm import CustomStreamWrapper
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as HangarLLMLoggingObj


class CustomLLMError(Exception):  # use this for all your exceptions
    def __init__(
        self,
        status_code,
        message,
    ):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)  # Call the base class constructor with the parameters it needs


class CustomLLM(BaseLLM):
    def __init__(self) -> None:
        super().__init__()

    def completion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        hangarllm_params=None,
        logger_fn=None,
        headers={},
        timeout: float | httpx.Timeout | None = None,
        client: HTTPHandler | None = None,
    ) -> Union[ModelResponse, "CustomStreamWrapper"]:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    def streaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        hangarllm_params=None,
        logger_fn=None,
        headers={},
        timeout: float | httpx.Timeout | None = None,
        client: HTTPHandler | None = None,
    ) -> Iterator[GenericStreamingChunk]:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    async def acompletion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        hangarllm_params=None,
        logger_fn=None,
        headers={},
        timeout: float | httpx.Timeout | None = None,
        client: AsyncHTTPHandler | None = None,
    ) -> (
        Coroutine[None, None, Union[ModelResponse, "CustomStreamWrapper"]] | Union[ModelResponse, "CustomStreamWrapper"]
    ):
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    async def astreaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: ModelResponse,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        hangarllm_params=None,
        logger_fn=None,
        headers={},
        timeout: float | httpx.Timeout | None = None,
        client: AsyncHTTPHandler | None = None,
    ) -> AsyncIterator[GenericStreamingChunk]:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    def image_generation(
        self,
        model: str,
        prompt: str,
        api_key: str | None,
        api_base: str | None,
        model_response: ImageResponse,
        optional_params: dict,
        logging_obj: "HangarLLMLoggingObj",
        timeout: float | httpx.Timeout | None = None,
        client: HTTPHandler | None = None,
    ) -> ImageResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    async def aimage_generation(
        self,
        model: str,
        prompt: str,
        model_response: ImageResponse,
        api_key: str | None,  # dynamically set api_key - https://github.com/valteresj2/HangarLLM#readme
        api_base: str | None,  # dynamically set api_base - https://github.com/valteresj2/HangarLLM#readme
        optional_params: dict,
        logging_obj: "HangarLLMLoggingObj",
        timeout: float | httpx.Timeout | None = None,
        client: AsyncHTTPHandler | None = None,
    ) -> ImageResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    def embedding(
        self,
        model: str,
        input: list,
        model_response: EmbeddingResponse,
        print_verbose: Callable,
        logging_obj: "HangarLLMLoggingObj",
        optional_params: dict,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        hangarllm_params=None,
    ) -> EmbeddingResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    async def aembedding(
        self,
        model: str,
        input: list,
        model_response: EmbeddingResponse,
        print_verbose: Callable,
        logging_obj: "HangarLLMLoggingObj",
        optional_params: dict,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        hangarllm_params=None,
    ) -> EmbeddingResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    def image_edit(
        self,
        model: str,
        image: Sequence[FileTypes],
        prompt: str | None,
        model_response: ImageResponse,
        api_key: str | None,
        api_base: str | None,
        optional_params: dict,
        logging_obj: "HangarLLMLoggingObj",
        timeout: float | httpx.Timeout | None = None,
        client: HTTPHandler | None = None,
    ) -> ImageResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")

    async def aimage_edit(
        self,
        model: str,
        image: Sequence[FileTypes],
        prompt: str | None,
        model_response: ImageResponse,
        api_key: str | None,
        api_base: str | None,
        optional_params: dict,
        logging_obj: "HangarLLMLoggingObj",
        timeout: float | httpx.Timeout | None = None,
        client: AsyncHTTPHandler | None = None,
    ) -> ImageResponse:
        raise CustomLLMError(status_code=500, message="Not implemented yet!")


def custom_chat_llm_router(async_fn: bool, stream: bool | None, custom_llm: CustomLLM):
    """
    Routes call to CustomLLM completion/acompletion/streaming/astreaming functions, based on call type

    Validates if response is in expected format
    """
    if async_fn:
        if stream:
            return custom_llm.astreaming
        return custom_llm.acompletion
    if stream:
        return custom_llm.streaming
    return custom_llm.completion
