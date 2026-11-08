from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.openai.image_generation.gpt_transformation import (
    GPTImageGenerationConfig,
)
from hangarllm.secret_managers.main import get_secret_str


class HangarLLMProxyImageGenerationConfig(GPTImageGenerationConfig):
    """Configuration for image generation requests routed through HangarLLM Proxy."""

    def validate_environment(
        self,
        headers: dict,
        model: str,
        messages,
        optional_params: dict,
        hangarllm_params: dict,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> dict:
        api_key = api_key or get_secret_str("HANGARLLM_PROXY_API_KEY")
        headers.update({"Authorization": f"Bearer {api_key}"})
        return headers

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict,
        hangarllm_params: dict,
        stream: bool | None = None,
    ) -> str:
        api_base = api_base or get_secret_str("HANGARLLM_PROXY_API_BASE")
        if api_base is None:
            raise ValueError("api_base not set for HangarLLM Proxy route. Set in env via `HANGARLLM_PROXY_API_BASE`")
        return join_api_base(api_base, "images/generations")
