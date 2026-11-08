"""
Base configuration class for Skills API
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.base_llm.chat.transformation import BaseLLMException
from hangarllm.types.llms.anthropic_skills import (
    CreateSkillRequest,
    DeleteSkillResponse,
    ListSkillsParams,
    ListSkillsResponse,
    Skill,
)
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.utils import LlmProviders

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any


class BaseSkillsAPIConfig(ABC):
    """Base configuration for Skills API providers"""

    def __init__(self):
        pass

    @property
    @abstractmethod
    def custom_llm_provider(self) -> LlmProviders:
        pass

    @abstractmethod
    def validate_environment(self, headers: dict, hangarllm_params: GenericHangarLLMParams | None) -> dict:
        """
        Validate and update headers with provider-specific requirements

        Args:
            headers: Base headers dictionary
            hangarllm_params: HangarLLM parameters

        Returns:
            Updated headers dictionary
        """
        return headers

    @abstractmethod
    def get_complete_url(
        self,
        api_base: str | None,
        endpoint: str,
        skill_id: str | None = None,
    ) -> str:
        """
        Get the complete URL for the API request

        Args:
            api_base: Base API URL
            endpoint: API endpoint (e.g., 'skills', 'skills/{id}')
            skill_id: Optional skill ID for specific skill operations

        Returns:
            Complete URL
        """
        if api_base is None:
            raise ValueError("api_base is required")
        return join_api_base(api_base, f"v1/{endpoint}")

    @abstractmethod
    def transform_create_skill_request(
        self,
        create_request: CreateSkillRequest,
        hangarllm_params: GenericHangarLLMParams,
        headers: dict,
    ) -> dict:
        """
        Transform create skill request to provider-specific format

        Args:
            create_request: Skill creation parameters
            hangarllm_params: HangarLLM parameters
            headers: Request headers

        Returns:
            Provider-specific request body
        """

    @abstractmethod
    def transform_create_skill_response(
        self,
        raw_response: httpx.Response,
        logging_obj: HangarLLMLoggingObj,
    ) -> Skill:
        """
        Transform provider response to Skill object

        Args:
            raw_response: Raw HTTP response
            logging_obj: Logging object

        Returns:
            Skill object
        """

    @abstractmethod
    def transform_list_skills_request(
        self,
        list_params: ListSkillsParams,
        hangarllm_params: GenericHangarLLMParams,
        headers: dict,
    ) -> tuple[str, dict]:
        """
        Transform list skills request parameters

        Args:
            list_params: List parameters (pagination, filters)
            hangarllm_params: HangarLLM parameters
            headers: Request headers

        Returns:
            Tuple of (url, query_params)
        """

    @abstractmethod
    def transform_list_skills_response(
        self,
        raw_response: httpx.Response,
        logging_obj: HangarLLMLoggingObj,
    ) -> ListSkillsResponse:
        """
        Transform provider response to ListSkillsResponse

        Args:
            raw_response: Raw HTTP response
            logging_obj: Logging object

        Returns:
            ListSkillsResponse object
        """

    @abstractmethod
    def transform_get_skill_request(
        self,
        skill_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        headers: dict,
    ) -> tuple[str, dict]:
        """
        Transform get skill request

        Args:
            skill_id: Skill ID
            api_base: Base API URL
            hangarllm_params: HangarLLM parameters
            headers: Request headers

        Returns:
            Tuple of (url, headers)
        """

    @abstractmethod
    def transform_get_skill_response(
        self,
        raw_response: httpx.Response,
        logging_obj: HangarLLMLoggingObj,
    ) -> Skill:
        """
        Transform provider response to Skill object

        Args:
            raw_response: Raw HTTP response
            logging_obj: Logging object

        Returns:
            Skill object
        """

    @abstractmethod
    def transform_delete_skill_request(
        self,
        skill_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        headers: dict,
    ) -> tuple[str, dict]:
        """
        Transform delete skill request

        Args:
            skill_id: Skill ID
            api_base: Base API URL
            hangarllm_params: HangarLLM parameters
            headers: Request headers

        Returns:
            Tuple of (url, headers)
        """

    @abstractmethod
    def transform_delete_skill_response(
        self,
        raw_response: httpx.Response,
        logging_obj: HangarLLMLoggingObj,
    ) -> DeleteSkillResponse:
        """
        Transform provider response to DeleteSkillResponse

        Args:
            raw_response: Raw HTTP response
            logging_obj: Logging object

        Returns:
            DeleteSkillResponse object
        """

    def get_error_class(
        self,
        error_message: str,
        status_code: int,
        headers: dict,
    ) -> Exception:
        """Get appropriate error class for the provider."""
        return BaseLLMException(
            status_code=status_code,
            message=error_message,
            headers=headers,
        )
