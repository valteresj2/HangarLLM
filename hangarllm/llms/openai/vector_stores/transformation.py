from typing import TYPE_CHECKING, Any, Final, cast

import httpx

import hangarllm
from hangarllm.hangarllm_core_utils.url_utils import encode_url_path_segment, join_api_base
from hangarllm.llms.base_llm.vector_store.transformation import BaseVectorStoreConfig
from hangarllm.llms.openai.workload_identity import resolve_openai_bearer_token
from hangarllm.secret_managers.main import get_secret_str
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.vector_stores import (
    BaseVectorStoreAuthCredentials,
    VectorStoreCreateOptionalRequestParams,
    VectorStoreCreateRequest,
    VectorStoreCreateResponse,
    VectorStoreIndexEndpoints,
    VectorStoreSearchOptionalRequestParams,
    VectorStoreSearchRequest,
    VectorStoreSearchResponse,
)
from hangarllm.utils import add_openai_metadata

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any


class OpenAIVectorStoreConfig(BaseVectorStoreConfig):
    ASSISTANTS_HEADER_KEY = "OpenAI-Beta"
    ASSISTANTS_HEADER_VALUE = "assistants=v2"

    def get_auth_credentials(self, hangarllm_params: dict) -> BaseVectorStoreAuthCredentials:
        api_key: Final = hangarllm_params.get("api_key")
        if api_key is None:
            raise ValueError("api_key is required")
        return {
            "headers": {
                "Authorization": f"Bearer {api_key}",
            },
        }

    def get_vector_store_endpoints_by_type(self) -> VectorStoreIndexEndpoints:
        return {
            "read": [("GET", "/vector_stores/{index_name}/search")],
            "write": [("POST", "/vector_stores")],
        }

    def validate_environment(self, headers: dict, hangarllm_params: GenericHangarLLMParams | None) -> dict:
        params: Final = hangarllm_params or GenericHangarLLMParams()
        bearer_token: Final = resolve_openai_bearer_token(
            api_key=params.api_key, api_base=params.api_base, hangarllm_params=params.model_dump(exclude_none=True)
        )
        headers.update(
            {
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            }
        )

        #########################################################
        # Ensure OpenAI Assistants header is includes
        #########################################################
        if self.ASSISTANTS_HEADER_KEY not in headers:
            headers.update(
                {
                    self.ASSISTANTS_HEADER_KEY: self.ASSISTANTS_HEADER_VALUE,
                }
            )

        return headers

    def get_complete_url(
        self,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        """
        Get the Base endpoint for OpenAI Vector Stores API
        """
        api_base = (
            api_base
            or hangarllm.api_base
            or get_secret_str("OPENAI_BASE_URL")
            or get_secret_str("OPENAI_API_BASE")
            or "https://api.openai.com/v1"
        )

        return join_api_base(api_base, "vector_stores")

    def transform_search_vector_store_request(
        self,
        vector_store_id: str,
        query: str | list[str],
        vector_store_search_optional_params: VectorStoreSearchOptionalRequestParams,
        api_base: str,
        hangarllm_logging_obj: HangarLLMLoggingObj,
        hangarllm_params: dict,
        extra_body: dict[str, object] | None = None,
    ) -> tuple[str, dict]:
        encoded_vector_store_id: Final = encode_url_path_segment(vector_store_id, field_name="vector_store_id")
        base_url, query_separator, query_string = api_base.partition("?")
        url: Final = f"{join_api_base(base_url, f'{encoded_vector_store_id}/search')}{query_separator}{query_string}"
        typed_request_body: Final = VectorStoreSearchRequest(
            query=query,
            filters=vector_store_search_optional_params.get("filters", None),
            max_num_results=vector_store_search_optional_params.get("max_num_results", None),
            ranking_options=vector_store_search_optional_params.get("ranking_options", None),
            rewrite_query=vector_store_search_optional_params.get("rewrite_query", None),
        )

        dict_request_body: Final = cast(dict, typed_request_body)
        return url, dict_request_body

    def transform_search_vector_store_response(
        self, response: httpx.Response, hangarllm_logging_obj: HangarLLMLoggingObj
    ) -> VectorStoreSearchResponse:
        try:
            response_json: Final = response.json()
            return VectorStoreSearchResponse(**response_json)
        except Exception as e:
            raise self.get_error_class(
                error_message=str(e),
                status_code=response.status_code,
                headers=response.headers,
            )

    def transform_create_vector_store_request(
        self,
        vector_store_create_optional_params: VectorStoreCreateOptionalRequestParams,
        api_base: str,
    ) -> tuple[str, dict]:
        url: Final = api_base  # Base URL for creating vector stores
        metadata: Final = vector_store_create_optional_params.get("metadata", None)
        metadata_payload: Final = add_openai_metadata(metadata)

        typed_request_body: Final = VectorStoreCreateRequest(
            name=vector_store_create_optional_params.get("name", None),
            file_ids=vector_store_create_optional_params.get("file_ids", None),
            expires_after=vector_store_create_optional_params.get("expires_after", None),
            chunking_strategy=vector_store_create_optional_params.get("chunking_strategy", None),
            metadata=metadata_payload,
        )

        dict_request_body: Final = cast(dict, typed_request_body)
        return url, dict_request_body

    def transform_create_vector_store_response(self, response: httpx.Response) -> VectorStoreCreateResponse:
        try:
            response_json: Final = response.json()
            return VectorStoreCreateResponse(**response_json)
        except Exception as e:
            raise self.get_error_class(
                error_message=str(e),
                status_code=response.status_code,
                headers=response.headers,
            )
