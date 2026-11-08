"""
OpenAI-like Responses API transformation.

Base class for JSON-declared providers that support the /v1/responses endpoint.
Inherits everything from OpenAIResponsesAPIConfig; subclasses only override
provider-specific resolution (slug, API key env var, base URL).
"""

from typing import Final

from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.openai.responses.transformation import OpenAIResponsesAPIConfig
from hangarllm.secret_managers.main import get_secret_str
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.utils import LlmProviders


class OpenAILikeResponsesConfig(OpenAIResponsesAPIConfig):
    """
    Responses API config for OpenAI-compatible providers declared via JSON.

    Concrete per-provider classes are generated dynamically in dynamic_config.py.
    This base provides the three overridable hooks that the dynamic generator
    fills in: custom_llm_provider, validate_environment, get_complete_url.
    """

    @property
    def custom_llm_provider(self) -> str | LlmProviders:
        return "openai_like"

    def validate_environment(
        self,
        headers: dict,
        model: str,
        hangarllm_params: GenericHangarLLMParams | None,
    ) -> dict:
        hangarllm_params = hangarllm_params or GenericHangarLLMParams()
        api_key: Final = hangarllm_params.api_key or get_secret_str("OPENAI_LIKE_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def get_complete_url(
        self,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        api_base = api_base or get_secret_str("OPENAI_LIKE_API_BASE")
        if not api_base:
            raise ValueError("api_base is required for openai_like provider")
        return join_api_base(api_base, "responses")
