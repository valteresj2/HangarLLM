"""
HangarLLM managed files, batches and fine-tuning jobs.

A *managed file* is uploaded once through the gateway (``target_model_names``)
and stored on every listed model deployment. Callers get back one opaque
**unified id**; the gateway keeps the per-deployment provider ids in
``HangarLLM_ManagedFileTable`` and swaps the right one in just before a request
reaches a deployment. Batches, fine-tuning jobs and background responses created
from managed files get unified ids too (``HangarLLM_ManagedObjectTable``), so a
client can create on one deployment and retrieve / cancel / bill later without
knowing where it ran.

Access control: only the creator (or, for service-account keys, the creator's
team) and proxy admins can read, use or delete a managed file / object.

Unified id formats (base64url, unpadded) follow ``SpecialEnums`` in core:

* file:   ``hangarllm_proxy:<mime>;unified_id,<uuid>;target_model_names,<m1,m2>``
* output: ``hangarllm_proxy:<mime>;unified_id,<uuid>;target_model_names,<m>;llm_output_file_id,<id>;llm_output_file_model_id,<model_id>``
* batch:  ``hangarllm_proxy;model_id:<model_id>;llm_batch_id:<provider batch id>``
* job:    ``hangarllm_proxy;model_id:<model_id>;generic_response_id:<provider job id>``
"""

import base64
import json
import time
import uuid
from collections.abc import Mapping, Sequence
from typing import Final, Literal

from fastapi import HTTPException

from hangarllm._logging import verbose_proxy_logger
from hangarllm.caching.dual_cache import DualCache
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.types.llms.openai import FileListPage, OpenAIFileObject
from hangarllm.types.utils import HangarLLMBatch, SpecialEnums

_CACHE_TTL_SECONDS: Final = 300
_UNIFIED_FILE_FIELDS: Final = ("input_file_id", "training_file", "validation_file", "file_id")
_FILE_ACCESS_CALL_TYPES: Final = frozenset({"afile_content", "afile_retrieve", "afile_delete", "file_content"})
_OBJECT_ACCESS_CALL_TYPES: Final = frozenset(
    {"aretrieve_batch", "acancel_batch", "aretrieve_fine_tuning_job", "acancel_fine_tuning_job"}
)


# ---------------------------------------------------------------------- id helpers
def _b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_unified_id(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        decoded: Final = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
    except Exception:  # noqa: BLE001
        return None
    return decoded if decoded.startswith(SpecialEnums.LITELM_MANAGED_FILE_ID_PREFIX.value) else None


def make_unified_file_id(content_type: str, target_model_names: Sequence[str]) -> str:
    return _b64(
        f"{SpecialEnums.LITELM_MANAGED_FILE_ID_PREFIX.value}:{content_type};unified_id,{uuid.uuid4()};"
        f"target_model_names,{','.join(target_model_names)}"
    )


def _role(user: UserAPIKeyAuth) -> str | None:
    role: Final = user.user_role
    return role.value if isinstance(role, HangarllmUserRoles) else role


def _is_admin(user: UserAPIKeyAuth) -> bool:
    return _role(user) in (HangarllmUserRoles.PROXY_ADMIN.value, HangarllmUserRoles.PROXY_ADMIN_VIEW_ONLY.value)


def _owner_matches(created_by: str | None, team_id: str | None, user: UserAPIKeyAuth) -> bool:
    if _is_admin(user):
        return True
    if user.user_id and created_by == user.user_id:
        return True
    # service-account keys (no user) own resources through their team
    return not user.user_id and bool(user.team_id) and team_id == user.team_id


def _json(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()  # type: ignore[union-attr]
    return json.dumps(value)


def _loads(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


class HangarManagedFiles(CustomLogger):
    def __init__(self, internal_usage_cache: object, prisma_client: object) -> None:
        super().__init__()
        cache: Final = getattr(internal_usage_cache, "dual_cache", internal_usage_cache)
        self.internal_usage_cache: DualCache = cache if isinstance(cache, DualCache) else DualCache()
        self.prisma_client = prisma_client

    # ------------------------------------------------------------------ repositories
    def _files(self):
        from hangarllm.repositories.managed_file_repository import ManagedFileRepository

        return ManagedFileRepository(self.prisma_client).table

    def _objects(self):
        from hangarllm.repositories.table_repositories import ManagedObjectRepository

        return ManagedObjectRepository(self.prisma_client).table

    # ------------------------------------------------------------------ id builders (public API)
    def get_unified_batch_id(self, batch_id: str, model_id: str) -> str:
        return _b64(SpecialEnums.HANGARLLM_MANAGED_BATCH_COMPLETE_STR.value.format(model_id, batch_id))

    def get_unified_generic_response_id(self, model_id: str, generic_response_id: str) -> str:
        return _b64(
            SpecialEnums.HANGARLLM_MANAGED_GENERIC_RESPONSE_COMPLETE_STR.value.format(model_id, generic_response_id)
        )

    def get_unified_output_file_id(self, output_file_id: str, model_id: str, model_name: str | None = None) -> str:
        return _b64(
            SpecialEnums.HANGARLLM_MANAGED_FILE_COMPLETE_STR.value.format(
                "application/json", uuid.uuid4(), model_name or "", output_file_id, model_id
            )
        )

    # ------------------------------------------------------------------ persistence
    async def store_unified_file_id(
        self,
        file_id: str,
        file_object: OpenAIFileObject | None,
        hangarllm_parent_otel_span: object,
        model_mappings: dict[str, str],
        user_api_key_dict: UserAPIKeyAuth,
        storage_backend: str | None = None,
        storage_url: str | None = None,
    ) -> None:
        data: Final = {
            "unified_file_id": file_id,
            "file_object": _json(file_object),
            "model_mappings": json.dumps(model_mappings),
            "flat_model_file_ids": list(model_mappings.values()),
            "created_by": user_api_key_dict.user_id,
            "updated_by": user_api_key_dict.user_id,
            "team_id": user_api_key_dict.team_id,
            "storage_backend": storage_backend,
            "storage_url": storage_url,
        }
        clean: Final = {k: v for k, v in data.items() if v is not None}
        await self._files().upsert(
            where={"unified_file_id": file_id},
            data={"create": clean, "update": {k: v for k, v in clean.items() if k != "unified_file_id"}},
        )
        await self.internal_usage_cache.async_set_cache(key=f"hangar:managed_file:{file_id}", value=None, ttl=1)

    async def get_unified_file_id(self, file_id: str, hangarllm_parent_otel_span: object = None):
        from hangarllm.models.managed_files import HangarLLM_ManagedFileTable

        cache_key: Final = f"hangar:managed_file:{file_id}"
        cached: Final = await self.internal_usage_cache.async_get_cache(key=cache_key)
        if isinstance(cached, dict):
            return HangarLLM_ManagedFileTable.model_validate(cached)
        row: Final = await self._files().find_first(where={"unified_file_id": file_id})
        if row is None:
            return None
        payload: Final = {
            "unified_file_id": row.unified_file_id,
            "file_object": _loads(row.file_object),
            "model_mappings": _loads(row.model_mappings) or {},
            "flat_model_file_ids": list(row.flat_model_file_ids or []),
            "created_by": row.created_by,
            "team_id": getattr(row, "team_id", None),
            "updated_by": row.updated_by,
            "storage_backend": getattr(row, "storage_backend", None),
            "storage_url": getattr(row, "storage_url", None),
        }
        await self.internal_usage_cache.async_set_cache(key=cache_key, value=payload, ttl=_CACHE_TTL_SECONDS)
        return HangarLLM_ManagedFileTable.model_validate(payload)

    async def store_unified_object_id(
        self,
        unified_object_id: str,
        file_object: object,
        hangarllm_parent_otel_span: object,
        model_object_id: str,
        file_purpose: Literal["batch", "fine-tune", "response", "container"],
        user_api_key_dict: UserAPIKeyAuth,
        request_tags: Sequence[str] | None = None,
        persist_attribution: bool = False,
        batch_processed: bool = False,
    ) -> None:
        status: Final = getattr(file_object, "status", None)
        data: dict[str, object] = {  # mutable-ok: prisma payload
            "unified_object_id": unified_object_id,
            "model_object_id": model_object_id,
            "file_object": _json(file_object),
            "file_purpose": file_purpose,
            "status": "complete" if status == "completed" else status,
            "created_by": user_api_key_dict.user_id,
            "updated_by": user_api_key_dict.user_id,
            "team_id": user_api_key_dict.team_id,
            "batch_processed": batch_processed,
            "api_key": user_api_key_dict.api_key,
            "org_id": user_api_key_dict.org_id,
            "end_user_id": user_api_key_dict.end_user_id,
            "request_tags": json.dumps(list(request_tags or [])),
        }
        clean: Final = {k: v for k, v in data.items() if v is not None}
        update: Final = {
            k: v for k, v in clean.items() if k in ("file_object", "status", "updated_by", "batch_processed")
        }
        await self._objects().upsert(
            where={"unified_object_id": unified_object_id}, data={"create": clean, "update": update}
        )

    async def store_batch_output_file(
        self,
        *,
        unified_file_id: str,
        provider_file_id: str,
        model_id: str | None,
        model_name: str | None = None,
        owner: UserAPIKeyAuth,
        hangarllm_parent_otel_span: object | None,
        size_bytes: int | None = None,
        fetch_provider_details: bool = True,
    ) -> None:
        file_object: Final = OpenAIFileObject(
            id=unified_file_id,
            bytes=size_bytes or 0,
            created_at=int(time.time()),
            filename="batch_output.jsonl",
            object="file",
            purpose="batch_output",
            status="processed",
        )
        await self.store_unified_file_id(
            file_id=unified_file_id,
            file_object=file_object,
            hangarllm_parent_otel_span=hangarllm_parent_otel_span,
            model_mappings={model_id or model_name or "unknown": provider_file_id},
            user_api_key_dict=owner,
        )

    async def get_unified_file_ids_for_provider_file_ids(
        self, provider_file_ids: Sequence[str], user_api_key_dict: UserAPIKeyAuth
    ) -> Mapping[str, str]:
        ids: Final = [p for p in provider_file_ids if p]
        if not ids:
            return {}
        rows: Final = await self._files().find_many(where={"flat_model_file_ids": {"hasSome": ids}})
        found: dict[str, str] = {}  # mutable-ok: provider id -> unified id
        for row in rows:
            if not _owner_matches(row.created_by, getattr(row, "team_id", None), user_api_key_dict):
                continue
            for provider_id in row.flat_model_file_ids or []:
                if provider_id in ids:
                    found[provider_id] = row.unified_file_id
        return found

    # ------------------------------------------------------------------ access control
    async def can_user_call_unified_file_id(self, unified_file_id: str, user_api_key_dict: UserAPIKeyAuth) -> bool:
        row: Final = await self._files().find_first(where={"unified_file_id": unified_file_id})
        if row is None:
            raise HTTPException(status_code=404, detail=f"File not found: {unified_file_id}")
        return _owner_matches(row.created_by, getattr(row, "team_id", None), user_api_key_dict)

    async def can_user_call_unified_object_id(self, unified_object_id: str, user_api_key_dict: UserAPIKeyAuth) -> bool:
        row: Final = await self._objects().find_first(where={"unified_object_id": unified_object_id})
        if row is None:
            raise HTTPException(status_code=404, detail=f"Object not found: {unified_object_id}")
        return _owner_matches(row.created_by, getattr(row, "team_id", None), user_api_key_dict)

    async def _require_file_access(self, file_id: str, user: UserAPIKeyAuth) -> None:
        if not await self.can_user_call_unified_file_id(file_id, user):
            raise HTTPException(status_code=403, detail=f"The caller does not have access to file {file_id}")

    # ------------------------------------------------------------------ files API
    async def acreate_file(
        self,
        create_file_request: Mapping[str, object],
        llm_router,
        target_model_names_list: list[str],
        hangarllm_parent_otel_span: object,
        user_api_key_dict: UserAPIKeyAuth,
    ) -> OpenAIFileObject:
        from hangarllm.hangarllm_core_utils.hidden_params import get_hidden_params
        from hangarllm.hangarllm_core_utils.prompt_templates.file_id_utils import extract_file_data

        if llm_router is None:
            raise HTTPException(status_code=500, detail="LLM router not initialised")
        mappings: dict[str, str] = {}  # mutable-ok: model_id -> provider file id
        first: OpenAIFileObject | None = None
        for model in target_model_names_list:
            response = await llm_router.acreate_file(model=model, **dict(create_file_request))
            hidden = get_hidden_params(response) or {}
            mapping = hidden.get("model_file_id_mapping")
            if isinstance(mapping, Mapping) and mapping:
                mappings.update({str(k): str(v) for k, v in mapping.items()})
            else:
                model_id = hidden.get("model_id") or model
                mappings[str(model_id)] = response.id
            first = first or response
        if first is None:
            raise HTTPException(status_code=400, detail="target_model_names must list at least one model")
        try:
            content_type = (
                extract_file_data(create_file_request["file"]).get("content_type") or "application/octet-stream"
            )  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            content_type = "application/octet-stream"
        unified_id: Final = make_unified_file_id(str(content_type), target_model_names_list)
        file_object: Final = OpenAIFileObject.model_validate({**first.model_dump(), "id": unified_id})
        await self.store_unified_file_id(
            file_id=unified_id,
            file_object=file_object,
            hangarllm_parent_otel_span=hangarllm_parent_otel_span,
            model_mappings=mappings,
            user_api_key_dict=user_api_key_dict,
        )
        return file_object

    async def _row_or_404(self, file_id: str):
        row: Final = await self.get_unified_file_id(file_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        return row

    async def afile_retrieve(self, file_id: str, hangarllm_parent_otel_span: object, llm_router=None) -> OpenAIFileObject:
        row: Final = await self._row_or_404(file_id)
        if row.file_object is not None:
            return OpenAIFileObject.model_validate({**row.file_object.model_dump(), "id": file_id})
        if llm_router is None or not row.model_mappings:
            raise HTTPException(status_code=404, detail=f"File object unavailable: {file_id}")
        model_id, provider_id = next(iter(row.model_mappings.items()))
        response: Final = await llm_router.afile_retrieve(model=model_id, file_id=provider_id)
        return OpenAIFileObject.model_validate({**response.model_dump(), "id": file_id})

    async def afile_list(
        self,
        purpose: str | None,
        hangarllm_parent_otel_span: object,
        user_api_key_dict: UserAPIKeyAuth | None = None,
        limit: int | None = None,
        after: str | None = None,
        model_scope=None,
        before: str | None = None,
        **data: object,
    ) -> FileListPage:
        where: dict[str, object] = {}  # mutable-ok: prisma filter
        if user_api_key_dict is not None and not _is_admin(user_api_key_dict):
            if user_api_key_dict.user_id:
                where["created_by"] = user_api_key_dict.user_id
            elif user_api_key_dict.team_id:
                where["team_id"] = user_api_key_dict.team_id
            else:
                return FileListPage()
        take: Final = max(1, min(limit or 20, 1000))
        rows: Final = await self._files().find_many(where=where, order={"created_at": "desc"}, take=take * 4 + 1)
        files: list[OpenAIFileObject] = []  # mutable-ok: page builder
        started = after is None
        for row in rows:
            if not started:
                started = row.unified_file_id == after
                continue
            if before is not None and row.unified_file_id == before:
                break
            mappings = _loads(row.model_mappings) or {}
            if model_scope is not None and not model_scope.holds(
                mappings.keys() if isinstance(mappings, dict) else (), stored=True
            ):
                continue
            obj = _loads(row.file_object)
            if not isinstance(obj, dict):
                continue
            if purpose and obj.get("purpose") != purpose:
                continue
            try:
                files.append(OpenAIFileObject.model_validate({**obj, "id": row.unified_file_id}))
            except Exception:  # noqa: BLE001, S112 - skip rows written by other versions
                continue
            if len(files) > take:
                break
        has_more: Final = len(files) > take
        page: Final = files[:take]
        return FileListPage(
            data=page,
            first_id=page[0].id if page else None,
            last_id=page[-1].id if page else None,
            has_more=has_more,
        )

    async def afile_delete(self, file_id: str, hangarllm_parent_otel_span: object, llm_router, **data: object):
        from openai.types.file_deleted import FileDeleted

        row: Final = await self._row_or_404(file_id)
        if llm_router is not None:
            for model_id, provider_id in row.model_mappings.items():
                try:
                    await llm_router.afile_delete(model=model_id, file_id=provider_id, **data)
                except Exception as e:  # noqa: BLE001 - keep deleting the other copies
                    verbose_proxy_logger.warning("HangarLLM: delete of %s on %s failed - %s", provider_id, model_id, e)
        await self._files().delete(where={"unified_file_id": file_id})
        await self.internal_usage_cache.async_set_cache(key=f"hangar:managed_file:{file_id}", value=None, ttl=1)
        return FileDeleted(id=file_id, deleted=True, object="file")

    async def afile_content(self, file_id: str, hangarllm_parent_otel_span: object, llm_router, **data: object):
        row: Final = await self._row_or_404(file_id)
        if llm_router is None or not row.model_mappings:
            raise HTTPException(status_code=404, detail=f"No deployment holds file {file_id}")
        last_error: Exception | None = None
        for model_id, provider_id in row.model_mappings.items():
            try:
                return await llm_router.afile_content(model=model_id, file_id=provider_id, **data)
            except Exception as e:  # noqa: BLE001 - try the next copy
                last_error = e
        raise HTTPException(status_code=502, detail=f"Could not read file {file_id}: {last_error}")

    # ------------------------------------------------------------------ batches
    async def list_user_batches(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        limit: int | None = None,
        after: str | None = None,
        provider: str | None = None,
        target_model_names: str | None = None,
        llm_router=None,
    ) -> Mapping[str, object]:
        where: dict[str, object] = {"file_purpose": "batch"}  # mutable-ok: prisma filter
        if not _is_admin(user_api_key_dict):
            if user_api_key_dict.user_id:
                where["created_by"] = user_api_key_dict.user_id
            elif user_api_key_dict.team_id:
                where["team_id"] = user_api_key_dict.team_id
            else:
                return {"object": "list", "data": [], "first_id": None, "last_id": None, "has_more": False}
        take: Final = max(1, min(limit or 20, 100))
        if after:
            anchor = await self._objects().find_first(where={"unified_object_id": after})
            if anchor is not None:
                where["created_at"] = {"lt": anchor.created_at}
        rows: Final = await self._objects().find_many(where=where, order={"created_at": "desc"}, take=take + 1)
        data: list[dict] = []  # mutable-ok: response page
        for row in rows[:take]:
            obj = _loads(row.file_object)
            if isinstance(obj, dict):
                data.append({**obj, "id": row.unified_object_id})
        return {
            "object": "list",
            "data": data,
            "first_id": data[0]["id"] if data else None,
            "last_id": data[-1]["id"] if data else None,
            "has_more": len(rows) > take,
        }

    # ------------------------------------------------------------------ background responses
    async def track_untracked_background_response(
        self,
        response_id: str,
        response: object,
        user_api_key_dict: UserAPIKeyAuth,
        request_tags: Sequence[str] | None = None,
    ) -> bool:
        """Record a finished background response that was never stored, so it is billed exactly once."""
        existing: Final = await self._objects().find_first(where={"unified_object_id": response_id})
        if existing is not None:
            return False
        await self.store_unified_object_id(
            unified_object_id=response_id,
            file_object=response,
            hangarllm_parent_otel_span=None,
            model_object_id=getattr(response, "id", response_id) or response_id,
            file_purpose="response",
            user_api_key_dict=user_api_key_dict,
            request_tags=request_tags,
            persist_attribution=True,
        )
        return True

    # ------------------------------------------------------------------ request hooks
    @staticmethod
    def _file_ids_in(value: object, found: list[str]) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key == "file_id" and isinstance(item, str):
                    found.append(item)
                else:
                    HangarManagedFiles._file_ids_in(item, found)
        elif isinstance(value, list):
            for item in value:
                HangarManagedFiles._file_ids_in(item, found)

    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache, data: dict, call_type):
        call: Final = str(getattr(call_type, "value", call_type))
        candidate_ids: list[str] = []  # mutable-ok: unified ids referenced by this request
        if call in _FILE_ACCESS_CALL_TYPES:
            file_id = data.get("file_id")
            if decode_unified_id(file_id):
                await self._require_file_access(str(file_id), user_api_key_dict)
            return data
        if call in _OBJECT_ACCESS_CALL_TYPES:
            id_field = "batch_id" if data.get("batch_id") else "fine_tuning_job_id"
            object_id = data.get(id_field)
            decoded = decode_unified_id(object_id)
            if not decoded:
                return data
            if not await self.can_user_call_unified_object_id(str(object_id), user_api_key_dict):
                raise HTTPException(status_code=403, detail=f"The caller does not have access to {object_id}")
            # route to the deployment that owns the object, with its provider-native id
            model_id = decoded.split("model_id:", 1)[1].split(";", 1)[0] if "model_id:" in decoded else None
            marker = "llm_batch_id:" if "llm_batch_id:" in decoded else "generic_response_id:"
            provider_id = decoded.split(marker, 1)[1].split(";", 1)[0] if marker in decoded else None
            if model_id and provider_id:
                data.setdefault("model", model_id)
                data[id_field] = provider_id
            return data
        for field in _UNIFIED_FILE_FIELDS:
            if decode_unified_id(data.get(field)):
                candidate_ids.append(str(data[field]))
        self._file_ids_in(data.get("messages"), candidate_ids)
        self._file_ids_in(data.get("input"), candidate_ids)
        unified: Final = [fid for fid in dict.fromkeys(candidate_ids) if decode_unified_id(fid)]
        if not unified:
            return data
        mapping: dict[str, dict[str, str]] = dict(data.get("model_file_id_mapping") or {})  # mutable-ok
        for fid in unified:
            await self._require_file_access(fid, user_api_key_dict)
            row = await self.get_unified_file_id(fid)
            if row is not None:
                mapping[fid] = dict(row.model_mappings)
        data["model_file_id_mapping"] = mapping
        return data

    async def async_pre_call_deployment_hook(self, kwargs: dict, call_type) -> dict | None:
        """Swap unified ids for the selected deployment's provider ids."""
        model_info: Final = kwargs.get("model_info")
        model_id: Final = model_info.get("id") if isinstance(model_info, Mapping) else None
        if not model_id:
            return kwargs
        mapping: Final = kwargs.get("model_file_id_mapping") or {}
        for field in _UNIFIED_FILE_FIELDS:
            value = kwargs.get(field)
            if not decode_unified_id(value):
                continue
            per_model = mapping.get(value) if isinstance(mapping, Mapping) else None
            if not isinstance(per_model, Mapping):
                row = await self.get_unified_file_id(str(value))
                per_model = row.model_mappings if row is not None else {}
            provider_id = per_model.get(model_id)
            if provider_id:
                kwargs[field] = provider_id
        return kwargs

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict: UserAPIKeyAuth, response):
        from hangarllm.hangarllm_core_utils.hidden_params import get_hidden_params

        hidden: Final = get_hidden_params(response) or {}
        retrieved_unified: Final = hidden.get("unified_batch_id")
        if isinstance(response, HangarLLMBatch) and isinstance(retrieved_unified, str) and retrieved_unified:
            # retrieve / cancel of a managed batch: hand the caller back its unified id
            if not decode_unified_id(response.id):
                response.id = _b64(retrieved_unified) if not decode_unified_id(retrieved_unified) else retrieved_unified
            return response
        model_id: Final = hidden.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            return response
        response_id: Final = getattr(response, "id", None)
        if not isinstance(response_id, str) or decode_unified_id(response_id):
            return response
        if isinstance(response, HangarLLMBatch) and hidden.get("batch_create") is True:
            unified_batch_id = self.get_unified_batch_id(batch_id=response_id, model_id=model_id)
            unified_input = hidden.get("unified_file_id")
            if isinstance(unified_input, str) and unified_input and decode_unified_id(response.input_file_id) is None:
                # hidden param carries the decoded form; the caller-facing id is the encoded one in the request
                requested_input = data.get("input_file_id")
                if decode_unified_id(requested_input):
                    response.input_file_id = str(requested_input)
            response.id = unified_batch_id
            await self.store_unified_object_id(
                unified_object_id=unified_batch_id,
                file_object=response,
                hangarllm_parent_otel_span=user_api_key_dict.parent_otel_span,
                model_object_id=response_id,
                file_purpose="batch",
                user_api_key_dict=user_api_key_dict,
                persist_attribution=True,
            )
            return response
        if type(response).__name__ == "HangarLLMFineTuningJob" and decode_unified_id(data.get("training_file")):
            unified_job_id = self.get_unified_generic_response_id(model_id=model_id, generic_response_id=response_id)
            response.id = unified_job_id
            response.training_file = data.get("training_file")
            await self.store_unified_object_id(
                unified_object_id=unified_job_id,
                file_object=response,
                hangarllm_parent_otel_span=user_api_key_dict.parent_otel_span,
                model_object_id=response_id,
                file_purpose="fine-tune",
                user_api_key_dict=user_api_key_dict,
                persist_attribution=True,
            )
        return response


# upstream-compatible names
_PROXY_HangarLLMManagedFiles = HangarManagedFiles
PROXY_HangarLLMManagedFiles = HangarManagedFiles
