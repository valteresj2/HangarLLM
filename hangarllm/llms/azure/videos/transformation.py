from typing import TYPE_CHECKING, Any

from hangarllm.llms.azure.common_utils import BaseAzureLLM
from hangarllm.llms.openai.videos.transformation import OpenAIVideoConfig
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.videos.main import VideoCreateOptionalRequestParams

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj

    from ...base_llm.chat.transformation import BaseLLMException as _BaseLLMException
    from ...base_llm.videos.transformation import BaseVideoConfig as _BaseVideoConfig

    HangarLLMLoggingObj = _HangarLLMLoggingObj
    BaseVideoConfig = _BaseVideoConfig
    BaseLLMException = _BaseLLMException
else:
    HangarLLMLoggingObj = Any
    BaseVideoConfig = Any
    BaseLLMException = Any


class AzureVideoConfig(OpenAIVideoConfig):
    """
    Configuration class for OpenAI video generation.
    """

    def __init__(self):
        super().__init__()

    def get_supported_openai_params(self, model: str) -> list:
        """
        Get the list of supported OpenAI parameters for video generation.
        """
        return [
            "model",
            "prompt",
            "input_reference",
            "seconds",
            "size",
            "user",
            "extra_headers",
        ]

    def map_openai_params(
        self,
        video_create_optional_params: VideoCreateOptionalRequestParams,
        model: str,
        drop_params: bool,
    ) -> dict:
        """No mapping applied since inputs are in OpenAI spec already"""
        return dict(video_create_optional_params)

    def validate_environment(
        self,
        headers: dict,
        model: str,
        api_key: str | None = None,
        hangarllm_params: GenericHangarLLMParams | None = None,
    ) -> dict:
        """
        Validate Azure environment and set up authentication headers.
        Uses _base_validate_azure_environment to properly handle credentials from hangarllm_credential_name.
        """
        # If hangarllm_params is provided, use it; otherwise create a new one
        if hangarllm_params is None:
            hangarllm_params = GenericHangarLLMParams()

        if api_key and not hangarllm_params.api_key:
            hangarllm_params.api_key = api_key

        # Use the base Azure validation method which properly handles:
        # 1. Credentials from hangarllm_credential_name via hangarllm_params
        # 2. Sets the correct "api-key" header (not "Authorization: Bearer")
        return BaseAzureLLM.base_validate_azure_environment(headers=headers, hangarllm_params=hangarllm_params)

    def get_complete_url(
        self,
        model: str,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        """
        Constructs a complete URL for the API request.
        """
        return BaseAzureLLM.get_base_azure_url(
            api_base=api_base,
            hangarllm_params=hangarllm_params,
            route="/openai/v1/videos",
            default_api_version="",
        )
