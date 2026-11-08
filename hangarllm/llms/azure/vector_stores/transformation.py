from typing import Final

from hangarllm.llms.azure.common_utils import BaseAzureLLM
from hangarllm.llms.openai.vector_stores.transformation import OpenAIVectorStoreConfig
from hangarllm.types.router import GenericHangarLLMParams


class AzureOpenAIVectorStoreConfig(OpenAIVectorStoreConfig):
    def get_complete_url(
        self,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        return BaseAzureLLM.get_base_azure_url(
            api_base=api_base,
            hangarllm_params=hangarllm_params,
            route="/openai/vector_stores",
        )

    def get_vector_store_url(self, api_base: str, encoded_vector_store_id: str) -> str:
        path, _, query = api_base.partition("?")
        url: Final = f"{path}/{encoded_vector_store_id}"
        return f"{url}?{query}" if query else url

    def validate_environment(self, headers: dict, hangarllm_params: GenericHangarLLMParams | None) -> dict:
        return BaseAzureLLM.base_validate_azure_environment(headers=headers, hangarllm_params=hangarllm_params)
