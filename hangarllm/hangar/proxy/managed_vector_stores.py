"""
Managed vector stores: ``POST /v1/vector_stores`` with ``target_model_names``
creates the store on every listed deployment and returns one unified id.
``file_search`` tools referencing that id are decoded to the provider id by core.
Built on core's ``BaseManagedResource`` (storage, access checks, listing).
"""

import uuid
from typing import Final

from fastapi import HTTPException

from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.llms.base_llm.managed_resources.base_managed_resource import BaseManagedResource
from hangarllm.llms.base_llm.managed_resources.isolation import can_access_resource
from hangarllm.llms.base_llm.managed_resources.utils import generate_unified_id_string, parse_unified_id
from hangarllm.proxy._types import UserAPIKeyAuth

_VECTOR_STORE_ID_CALL_TYPES: Final = frozenset(
    {"avector_store_search", "avector_store_retrieve", "avector_store_update", "avector_store_delete"}
)


class HangarManagedVectorStores(CustomLogger, BaseManagedResource[object]):
    def __init__(self, internal_usage_cache, prisma_client) -> None:
        CustomLogger.__init__(self)
        BaseManagedResource.__init__(self, internal_usage_cache=internal_usage_cache, prisma_client=prisma_client)

    @property
    def resource_type(self) -> str:
        return "vector_store"

    @property
    def table_name(self) -> str:
        return "hangarllm_managedvectorstoretable"

    async def denies_access(self, unified_id: str, user_api_key_dict: UserAPIKeyAuth) -> bool:
        resource: Final = await self.get_unified_resource_id(unified_id)
        return resource is not None and not can_access_resource(
            user_api_key_dict=user_api_key_dict,
            created_by=resource.get("created_by"),
            resource_team_id=resource.get("team_id"),
        )

    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache, data: dict, call_type):
        vector_store_id: Final = data.get("vector_store_id")
        if str(getattr(call_type, "value", call_type)) not in _VECTOR_STORE_ID_CALL_TYPES:
            return data
        parsed: Final = parse_unified_id(vector_store_id) if isinstance(vector_store_id, str) else None
        if not parsed or parsed.get("resource_type") != self.resource_type:
            return data
        if not await self.can_user_access_unified_resource_id(vector_store_id, user_api_key_dict):
            raise HTTPException(
                status_code=403, detail=f"The caller does not have access to vector store {vector_store_id}"
            )
        model_id: Final = parsed.get("model_id")
        provider_id: Final = parsed.get("provider_resource_id")
        if not model_id or not provider_id:
            return data
        return {"model": model_id, **data, "vector_store_id": provider_id}

    def get_unified_resource_id_format(self, resource_object: object, target_model_names_list: list[str]) -> str:
        hidden: Final = getattr(resource_object, "_hidden_params", {}) or {}
        return generate_unified_id_string(
            resource_type=self.resource_type,
            unified_uuid=str(uuid.uuid4()),
            target_model_names=target_model_names_list,
            provider_resource_id=str(getattr(resource_object, "id", "")),
            model_id=str(hidden.get("model_id", "")),
        )

    async def create_resource_for_model(
        self, llm_router, model: str, request_data: dict, hangarllm_parent_otel_span
    ) -> object:
        response: Final = await llm_router.avector_store_create(model=model, **request_data)
        hidden = getattr(response, "_hidden_params", None)
        if not isinstance(hidden, dict):
            hidden = {}
            try:
                response._hidden_params = hidden  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001, S110 - immutable response objects keep no hidden params
                pass
        model_id: Final = hidden.get("model_id") or model
        hidden.setdefault("model_resource_id_mapping", {model_id: getattr(response, "id", "")})
        return response

    async def acreate_vector_store(
        self,
        create_request: dict,
        llm_router,
        target_model_names_list: list[str],
        hangarllm_parent_otel_span,
        user_api_key_dict: UserAPIKeyAuth,
    ) -> object:
        request_data: Final = {k: v for k, v in dict(create_request).items() if k != "target_model_names"}
        responses: Final = await self.create_resource_for_each_model(
            llm_router=llm_router,
            request_data=request_data,
            target_model_names_list=[str(m) for m in target_model_names_list],
            hangarllm_parent_otel_span=hangarllm_parent_otel_span,
        )
        unified_id: Final = self.generate_unified_resource_id(responses, [str(m) for m in target_model_names_list])
        mappings: Final = self.extract_model_mappings_from_responses(responses)
        first: Final = responses[0]
        try:
            first.id = unified_id  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - dict-like responses
            if isinstance(first, dict):
                first["id"] = unified_id
        await self.store_unified_resource_id(
            unified_resource_id=unified_id,
            resource_object=first,
            hangarllm_parent_otel_span=hangarllm_parent_otel_span,
            model_mappings=mappings,
            user_api_key_dict=user_api_key_dict,
        )
        return first
