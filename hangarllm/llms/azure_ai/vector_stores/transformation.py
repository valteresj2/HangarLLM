from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

import httpx

from hangarllm.hangarllm_core_utils.url_utils import join_api_base
from hangarllm.llms.azure.common_utils import BaseAzureLLM
from hangarllm.llms.base_llm.vector_store.transformation import (
    BaseQueryEmbeddingVectorStoreConfig,
    VectorStoreEmbeddingExecutor,
)
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


class AzureAIVectorStoreConfig(BaseQueryEmbeddingVectorStoreConfig, BaseAzureLLM):
    """
    Configuration for Azure AI Search Vector Store

    This implementation uses the Azure AI Search API for vector store operations.
    Supports vector search with embeddings generated via hangarllm.embeddings.
    """

    def __init__(self):
        super().__init__()

    def get_vector_store_endpoints_by_type(self) -> VectorStoreIndexEndpoints:
        """
        Every ``GET`` under ``/indexes/`` is a read: get details, stats, and the
        document reads (GET-form search, ``$count``, point lookup, and the
        GET forms of suggest and autocomplete).

        ``POST`` splits by endpoint. Search, suggest, autocomplete, and analyze
        are query endpoints, so they read; ``/docs/index`` is the batch endpoint
        carrying upload, merge, mergeOrUpload, and delete actions, so it writes.

        Patterns stay literal rather than ``{placeholder}`` templates because the
        matcher falls back to the substring before a ``{``, which here is always
        ``/indexes/``. The matcher is substring-based, so an index name may
        itself contain a read fragment (an index named ``analyze*`` puts
        ``/analyze`` inside the batch-write path); writes are classified before
        reads, so such a path demands the write grant rather than being
        shadowed into a read.
        """
        return {
            "read": [
                ("GET", "/indexes/"),
                ("POST", "/docs/search"),
                ("POST", "/docs/suggest"),
                ("POST", "/docs/autocomplete"),
                ("POST", "/analyze"),
            ],
            "write": [("POST", "/docs/index")],
        }

    def get_auth_credentials(self, hangarllm_params: dict) -> BaseVectorStoreAuthCredentials:
        api_key: Final = hangarllm_params.get("api_key")
        if api_key is None:
            raise ValueError("api_key is required")

        return {
            "headers": {
                "api-key": api_key,
            }
        }

    def validate_environment(self, headers: dict, hangarllm_params: GenericHangarLLMParams | None) -> dict:
        basic_headers: Final = self._base_validate_azure_environment(headers, hangarllm_params)
        basic_headers.update({"Content-Type": "application/json"})
        return basic_headers

    def get_complete_url(
        self,
        api_base: str | None,
        hangarllm_params: dict,
    ) -> str:
        """
        Get the base endpoint for Azure AI Search API

        Expected format: https://{search_service_name}.search.windows.net
        """
        if api_base:
            return api_base.rstrip("/")

        # Get search service name from hangarllm_params
        search_service_name: Final = hangarllm_params.get("azure_search_service_name")

        if not search_service_name:
            raise ValueError(
                "Azure AI Search service name is required. "
                "Provide it via hangarllm_params['azure_search_service_name'] or api_base parameter"
            )

        # Azure AI Search endpoint
        return f"https://{search_service_name}.search.windows.net"

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
        vector_field: Final = hangarllm_params.get("azure_search_vector_field", "contentVector")
        top_k: Final = vector_store_search_optional_params.get("top_k", 10)
        hangarllm_logging_obj.model_call_details["input"] = query_text
        hangarllm_logging_obj.model_call_details["embedding_model"] = hangarllm_params.get("hangarllm_embedding_model")
        hangarllm_logging_obj.model_call_details["top_k"] = top_k
        search_route: Final = f"indexes/{vector_store_id}/docs/search"
        return f"{join_api_base(api_base, search_route)}?api-version=2024-07-01", {
            "search": "*",
            "vectorQueries": [{"vector": query_vector, "fields": vector_field, "kind": "vector", "k": top_k}],
            "select": "id,content",
            "top": top_k,
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
                    "@search.score": 0.95,
                    ... (other fields)
                }
            ]
        }
        """
        try:
            response_json: Final = response.json()

            # Extract results from Azure AI Search API response
            results: Final = response_json.get("value", [])

            # Transform results to standard format
            search_results: Final[list[VectorStoreSearchResult]] = []
            for result in results:
                # Extract document ID
                document_id = result.get("id", "")

                # Extract text content
                text_content = result.get("content", "")

                content = [
                    VectorStoreResultContent(
                        text=text_content,
                        type="text",
                    )
                ]

                # Get the search score (relevance score from Azure AI Search)
                score = result.get("@search.score", 0.0)

                # Use document ID as both file_id and filename
                file_id = document_id
                filename = f"Document {document_id}"

                # Build attributes with all available metadata
                # Exclude system fields and already-processed fields
                attributes = {}
                for key, value in result.items():
                    if key not in ["id", "content", "contentVector", "@search.score"]:
                        attributes[key] = value

                # Always include document_id in attributes
                attributes["document_id"] = document_id

                result_obj = VectorStoreSearchResult(
                    score=score,
                    content=content,
                    file_id=file_id,
                    filename=filename,
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
