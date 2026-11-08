from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.openai.image_edit.transformation import OpenAIImageEditConfig
from hangarllm.secret_managers.main import get_secret_str


class HangarLLMProxyImageEditConfig(OpenAIImageEditConfig):
    """Configuration for image edit requests routed through HangarLLM Proxy."""

    def validate_environment(
        self,
        headers: dict,
        model: str,
        api_key: str | None = None,
        hangarllm_params: dict | None = None,
        api_base: str | None = None,
    ) -> dict:
        api_key = api_key or get_secret_str("HANGARLLM_PROXY_API_KEY")
        headers.update({"Authorization": f"Bearer {api_key}"})
        return headers

    def get_complete_url(self, model: str, api_base: str | None, hangarllm_params: dict) -> str:
        api_base = api_base or get_secret_str("HANGARLLM_PROXY_API_BASE")
        if api_base is None:
            raise ValueError("api_base not set for HangarLLM Proxy route. Set in env via `HANGARLLM_PROXY_API_BASE`")
        return join_api_base(api_base, "images/edits")
