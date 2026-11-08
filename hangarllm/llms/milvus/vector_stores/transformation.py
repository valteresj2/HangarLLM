from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

import httpx
from pydantic import TypeAdapter

from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.base_llm.vector_store.transformation import (
    BaseQueryEmbeddingVectorStoreConfig,
    VectorStoreEmbeddingExecutor,
)
from hangarllm.llms.openai.common_utils import decoded_json_object
from hangarllm.secret_managers.main import get_secret_str
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.vector_stores import (
    BaseVectorStoreAuthCredentials,
    VectorStoreCreateOptionalRequestParams,
    VectorStoreCreateResponse,
    VectorStoreIndexEndpoints,
    VectorStoreResultContent,
    VectorStoreSearchOptionalRequestParams,
    VectorStoreSearchResponse,
    VectorStoreSearchResult,
)

if TYPE_CHECKING:
    from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as _HangarLLMLoggingObj

    HangarLLMLoggingObj = _HangarLLMLoggingObj
else:
    HangarLLMLoggingObj = Any

_DECODED_JSON: Final = TypeAdapter(object)

MILVUS_OPTIONAL_PARAMS: Final = {
    "annsField",
    "limit",
    "filter",
    "offset",
    "groupingField",
    "outputFields",
    "searchParams",
    "consistencyLevel",
}


class MilvusVectorStoreConfig(BaseQueryEmbeddingVectorStoreConfig):
    """
    Configuration for Milvus Vector Store

    This implementation uses the Azure AI Search API for vector store operations.
    Supports vector search with embeddings generated via hangarllm.embeddings.
    """

    def __init__(self):
        super().__init__()

    def validate_environment(self, headers: dict, hangarllm_params: GenericHangarLLMParams | None) -> dict:
        api_key: str | None = None
        if hangarllm_params is not None:
            api_key = hangarllm_params.api_key or get_secret_str("MILVUS_API_KEY")

        if not api_key:
            raise ValueError(
                "MILVUS_API_KEY is not set. Either set it in the hangarllm_params or set the MILVUS_API_KEY environment variable."
            )

        headers.update({"Authorization": f"Bearer {api_key}"})

        return headers

    def get_auth_credentials(self, hangarllm_params: dict) -> BaseVectorStoreAuthCredentials:
        api_key: Final = hangarllm_params.get("api_key")
        if not api_key:
            raise ValueError(
                "MILVUS_API_KEY is not set. Either set it in the hangarllm_params or set the MILVUS_API_KEY environment variable."
            )
        return {
            "headers": {
                "Authorization": f"Bearer {api_key}",
            },
        }

    def get_vector_store_endpoints_by_type(self) -> VectorStoreIndexEndpoints:
        return {
            "read": [
                ("POST", "/v2/vectordb/entities/search"),
                ("POST", "/v2/vectordb/entities/get"),
                ("POST", "/v2/vectordb/entities/query"),
            ],
            "write": [
                ("POST", "/v2/vectordb/entities/upsert"),
                ("POST", "/v2/vectordb/entities/insert"),
            ],
        }

    def map_openai_params(self, non_default_params: dict, optional_params: dict, drop_params: bool) -> dict:
        for param, value in non_default_params.items():
            if param in MILVUS_OPTIONAL_PARAMS:
                optional_params[param] = value
        return optional_params

    def get_complete_url(
        self,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        """
        Get the base endpoint for Milvus API

        Expected format: https://{milvus_api_base}.milvus.io
        """
        api_base = api_base or get_secret_str("MILVUS_API_BASE")

        if not api_base:
            raise ValueError(
                "Milvus API base URL is required. Set MILVUS_API_BASE environment variable or pass api_base in hangarllm_params."
            )

        if api_base:
            return api_base.rstrip("/")

        return api_base

    def transform_search_vector_store_request(
        self,
        vector_store_id: str,
        query: str | Sequence[str],
        vector_store_search_optional_params: VectorStoreSearchOptionalRequestParams,
        api_base: str,
        hangarllm_logging_obj: HangarLLMLoggingObj,
        hangarllm_params: Mapping[str, object],
        extra_body: Mapping[str, object] | None = None,
        embedding_executor: VectorStoreEmbeddingExecutor | None = None,
    ) -> tuple[str, dict[str, object]]:
        query_text: Final = self.query_text(query)
        query_vector: Final = self.embed_query(query_text, hangarllm_params, embedding_executor)
        return self._search_request(
            vector_store_id,
            query_text,
            query_vector,
            vector_store_search_optional_params,
            api_base,
            hangarllm_logging_obj,
            hangarllm_params,
        )

    async def atransform_search_vector_store_request(
        self,
        vector_store_id: str,
        query: str | Sequence[str],
        vector_store_search_optional_params: VectorStoreSearchOptionalRequestParams,
        api_base: str,
        hangarllm_logging_obj: HangarLLMLoggingObj,
        hangarllm_params: Mapping[str, object],
        extra_body: Mapping[str, object] | None = None,
        embedding_executor: VectorStoreEmbeddingExecutor | None = None,
    ) -> tuple[str, dict[str, object]]:
        query_text: Final = self.query_text(query)
        query_vector: Final = await self.aembed_query(query_text, hangarllm_params, embedding_executor)
        return self._search_request(
            vector_store_id,
            query_text,
            query_vector,
            vector_store_search_optional_params,
            api_base,
            hangarllm_logging_obj,
            hangarllm_params,
        )

    @staticmethod
    def _search_request(
        vector_store_id: str,
        query_text: str,
        query_vector: Sequence[float],
        vector_store_search_optional_params: VectorStoreSearchOptionalRequestParams,
        api_base: str,
        hangarllm_logging_obj: HangarLLMLoggingObj,
        hangarllm_params: Mapping[str, object],
    ) -> tuple[str, dict[str, object]]:
        scope: Final = {
            key: value
            for key, value in (
                ("dbName", hangarllm_params.get("milvus_db_name")),
                ("partitionNames", hangarllm_params.get("milvus_partition_names")),
            )
            if value
        }
        hangarllm_logging_obj.model_call_details["input"] = query_text
        hangarllm_logging_obj.model_call_details["embedding_model"] = hangarllm_params.get("hangarllm_embedding_model")
        return join_api_base(api_base, "v2/vectordb/entities/search"), {
            "collectionName": vector_store_id,
            "data": [query_vector],
            "annsField": "book_intro_vector",
            **vector_store_search_optional_params,
            **scope,
        }

    def transform_search_vector_store_response(
        self, response: httpx.Response, hangarllm_logging_obj: HangarLLMLoggingObj
    ) -> VectorStoreSearchResponse:
        """
        Transform Azure AI Search API response to standard vector store search response

        Handles the format from Azure AI Search which returns:
        {
            "value": [
                {
                    "id": "...",
                    "content": "...",
                    "distance": 0.95,
                }
            ]
        }
        """
        try:
            response_json: Final = response.json()

            # Extract results from Azure AI Search API response
            results: Final = response_json.get("data", [])

            # Try to get text_field from optional_params first, then hangarllm_params
            optional_params: Final = decoded_json_object(
                _DECODED_JSON.validate_python(hangarllm_logging_obj.model_call_details.get("optional_params", {}))
            )
            text_field = optional_params.get("milvus_text_field", "")

            # Fallback to hangarllm_params if not in optional_params

            if not text_field:
                text_field = decoded_json_object(
                    _DECODED_JSON.validate_python(hangarllm_logging_obj.model_call_details.get("hangarllm_params", {}))
                ).get("milvus_text_field", "")

            # Transform results to standard format
            search_results: Final[list[VectorStoreSearchResult]] = []
            for result in results:
                # Extract text content
                text_content = result.get(text_field, "")

                content = [
                    VectorStoreResultContent(
                        text=text_content,
                        type="text",
                    )
                ]

                # Get the search score (distance from the query vector)
                score = result.get("distance", 0.0)

                # Build attributes with all available metadata
                # Exclude system fields and already-processed fields
                attributes = {
                    key: value
                    for key, value in decoded_json_object(_DECODED_JSON.validate_python(result)).items()
                    if key not in ["id", "content", "distance", text_field]
                }

                result_obj = VectorStoreSearchResult(
                    score=score,
                    content=content,
                    file_id=None,
                    filename=None,
                    attributes=attributes,
                )
                search_results.append(result_obj)

            return VectorStoreSearchResponse(
                object="vector_store.search_results.page",
                search_query=hangarllm_logging_obj.model_call_details.get("input", ""),
                data=search_results,
            )

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
        raise NotImplementedError

    def transform_create_vector_store_response(self, response: httpx.Response) -> VectorStoreCreateResponse:
        raise NotImplementedError
