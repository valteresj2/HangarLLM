"""
Background cost reconciliation.

``CheckBatchCost``
    Every ``PROXY_BATCH_POLLING_INTERVAL`` seconds, finds managed batches whose
    cost has not been accounted yet, re-reads them from the deployment that runs
    them and - once a batch reaches a final state - lets core's logging pipeline
    price the output file and write the spend log under the original key / team /
    org / tags. The batch is then marked ``batch_processed`` so it is billed once.

``CheckResponsesCost``
    Polls background (``background: true``) Responses API calls stored as managed
    objects. A create bills nothing, so the first caller to see a response finished
    (this poll, a read, a stream) claims the row and logs the one billing event for it.
"""

import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

import hangarllm
from hangarllm._logging import verbose_proxy_logger
from hangarllm.constants import (
    INTERNAL_CALL_ORIGIN_METADATA_KEY,
    MAX_OBJECTS_PER_POLL_CYCLE,
    TERMINAL_RESPONSE_STATUSES,
)
from hangarllm.hangarllm_core_utils.hangarllm_logging import _CUSTOM_PRICING_KEYS, Logging
from hangarllm.responses.utils import ResponsesAPIRequestUtils
from hangarllm.types.responses.main import DecodedResponseId
from hangarllm.types.utils import BACKGROUND_RESPONSE_COST_POLL_CALL_ORIGIN, BACKGROUND_RESPONSE_STATUS_POLL_CALL_ORIGIN

GIVE_UP_POLLING_AFTER: Final = timedelta(days=7)
_PAGE_SIZE: Final = 50
_TERMINAL_BATCH_STATUSES: Final = frozenset({"completed", "complete", "failed", "cancelled", "expired"})
_PENDING_RESPONSE_STATUSES: Final = ("queued", "in_progress")
_STALE_RESPONSE_STATUS: Final = "stale_expired"


def _decoded_response_id(response_id: str) -> DecodedResponseId:
    return ResponsesAPIRequestUtils.decode_responses_api_response_id(response_id)


def _decoded(unified_id: str) -> str | None:
    from hangarllm.proxy.openai_files_endpoints.common_utils import is_base64_encoded_unified_file_id

    decoded: Final = is_base64_encoded_unified_file_id(unified_id)
    return decoded or None


def _owner_metadata(row: object) -> dict[str, object]:
    import json

    tags_raw: Final = getattr(row, "request_tags", None)
    tags: object = tags_raw
    if isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw)
        except ValueError:
            tags = []
    return {
        "user_api_key": getattr(row, "api_key", None),
        "user_api_key_user_id": getattr(row, "created_by", None),
        "user_api_key_team_id": getattr(row, "team_id", None),
        "user_api_key_org_id": getattr(row, "org_id", None),
        "user_api_key_end_user_id": getattr(row, "end_user_id", None),
        "tags": tags if isinstance(tags, list) else [],
        "batch_cost_poller": True,
    }


class CheckBatchCost:
    def __init__(self, proxy_logging_obj, prisma_client, llm_router, track_unmanaged_batch_cost: bool = False) -> None:
        self.proxy_logging_obj = proxy_logging_obj
        self.prisma_client = prisma_client
        self.llm_router = llm_router
        self.track_unmanaged_batch_cost: bool = track_unmanaged_batch_cost
        # core reads this to decide whether the retrieve path should account inline
        self.batch_processed_support_confirmed: bool = False
        self._column_absent: bool = False

    def _table(self):
        from hangarllm.repositories.table_repositories import ManagedObjectRepository

        return ManagedObjectRepository(self.prisma_client).table

    async def confirm_batch_processed_support(self) -> None:
        """Probe the ``batch_processed`` column once; only then does the poller own batch accounting."""
        if self.prisma_client is None:
            return
        try:
            await self._table().find_first(where={"batch_processed": False})
            self.batch_processed_support_confirmed = True
        except Exception as e:  # noqa: BLE001
            if "batch_processed" in str(e).lower():
                self._column_absent = True
                verbose_proxy_logger.warning("HangarLLM: batch_processed column missing - run DB migrations")
            else:
                verbose_proxy_logger.debug("HangarLLM: batch_processed probe deferred - %s", e)

    async def _pending_rows(self) -> list:
        cutoff: Final = datetime.now(timezone.utc) - GIVE_UP_POLLING_AFTER
        where: dict[str, object] = {"file_purpose": "batch", "created_at": {"gte": cutoff}}  # mutable-ok
        if self._column_absent:
            where["status"] = {"not_in": sorted(_TERMINAL_BATCH_STATUSES)}
        else:
            where["batch_processed"] = False
        return list(await self._table().find_many(where=where, order={"created_at": "asc"}, take=_PAGE_SIZE))

    async def check_batch_cost(self) -> None:
        if self.prisma_client is None or self.llm_router is None:
            return
        if not self.batch_processed_support_confirmed and not self._column_absent:
            await self.confirm_batch_processed_support()
        try:
            rows: Final = await self._pending_rows()
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.error("HangarLLM CheckBatchCost: query failed - %s", e)
            return
        for row in rows:
            try:
                await self._reconcile(row)
            except Exception as e:  # noqa: BLE001 - one bad batch must not stop the sweep
                verbose_proxy_logger.warning(
                    "HangarLLM CheckBatchCost: batch %s skipped - %s", row.unified_object_id, e
                )

    async def _reconcile(self, row: object) -> None:
        from hangarllm.proxy.openai_files_endpoints.common_utils import (
            get_batch_id_from_unified_batch_id,
            get_model_id_from_unified_batch_id,
            is_hangarllm_executed_batch,
        )

        unified_id: Final = str(row.unified_object_id)
        decoded: Final = _decoded(unified_id)
        if decoded is None or is_hangarllm_executed_batch(decoded):
            return  # gateway-executed batches bill themselves
        model_id: Final = get_model_id_from_unified_batch_id(decoded)
        provider_batch_id: Final = get_batch_id_from_unified_batch_id(decoded)
        if not model_id or not provider_batch_id:
            return
        batch: Final = await self.llm_router.aretrieve_batch(
            model=model_id,
            batch_id=provider_batch_id,
            hangarllm_metadata={**_owner_metadata(row), "model_group": model_id},
        )
        status: Final = str(getattr(batch, "status", "") or "")
        update: dict[str, object] = {  # mutable-ok: prisma payload
            "status": "complete" if status == "completed" else status,
            "file_object": batch.model_dump_json(),
        }
        if status in _TERMINAL_BATCH_STATUSES:
            from hangarllm.hangarllm_core_utils.batch_utils import batch_cost_is_final

            final: Final = status != "completed" or batch_cost_is_final(batch)
            if final and not self._column_absent:
                update["batch_processed"] = True
        await self._table().update(where={"unified_object_id": unified_id}, data=update)


@dataclass(frozen=True, slots=True)
class _BilledCharge:
    cost: float | None
    logging_obj: object


def _row_file_object(row: object) -> Mapping[str, object] | None:
    raw: Final = getattr(row, "file_object", None)
    if isinstance(raw, str):
        try:
            parsed: Final = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, Mapping) else None
    return raw if isinstance(raw, Mapping) else None


class CheckResponsesCost:
    def __init__(self, proxy_logging_obj, prisma_client, llm_router) -> None:
        self.proxy_logging_obj = proxy_logging_obj
        self.prisma_client = prisma_client
        self.llm_router = llm_router

    def _table(self):
        from hangarllm.repositories.table_repositories import ManagedObjectRepository

        return ManagedObjectRepository(self.prisma_client).table

    async def check_responses_cost(self) -> None:
        if self.prisma_client is None:
            return
        await self._retire_stale_rows()
        try:
            rows: Final = await self._table().find_many(
                where={"status": {"in": list(_PENDING_RESPONSE_STATUSES)}, "file_purpose": "response"},
                take=MAX_OBJECTS_PER_POLL_CYCLE,
                order={"created_at": "asc"},
            )
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.error("HangarLLM CheckResponsesCost: query failed - %s", e)
            return
        for row in rows:
            try:
                await self._poll(row)
            except Exception as e:  # noqa: BLE001 - one bad response must not stop the sweep
                verbose_proxy_logger.warning(
                    "HangarLLM CheckResponsesCost: response %s skipped - %s", row.unified_object_id, e
                )

    async def _retire_stale_rows(self) -> None:
        cutoff: Final = datetime.now(timezone.utc) - GIVE_UP_POLLING_AFTER
        try:
            await self._table().update_many(
                where={
                    "file_purpose": "response",
                    "status": {"in": list(_PENDING_RESPONSE_STATUSES)},
                    "created_at": {"lt": cutoff},
                },
                data={"status": _STALE_RESPONSE_STATUS},
            )
        except Exception as e:  # noqa: BLE001 - retirement is housekeeping, polling continues without it
            verbose_proxy_logger.debug("HangarLLM CheckResponsesCost: stale cleanup failed - %s", e)

    def _deployment_of(self, response_id: str) -> object | None:
        model_id: Final = _decoded_response_id(response_id).get("model_id")
        if not model_id or self.llm_router is None:
            return None
        return self.llm_router.registry().deployment(model_id)

    async def _read_response(self, response_id: str, owner_metadata: Mapping[str, object]) -> object:
        metadata: Final = {
            **owner_metadata,
            INTERNAL_CALL_ORIGIN_METADATA_KEY: BACKGROUND_RESPONSE_STATUS_POLL_CALL_ORIGIN,
        }
        if self._deployment_of(response_id) is not None:
            return await self.llm_router.aget_responses(response_id=response_id, hangarllm_metadata=metadata)
        return await hangarllm.aget_responses(
            response_id=response_id,
            custom_llm_provider=_decoded_response_id(response_id).get("custom_llm_provider") or "openai",
            hangarllm_metadata=metadata,
        )

    async def _poll(self, row: object) -> None:
        if _row_file_object(row) is None:
            verbose_proxy_logger.warning("HangarLLM CheckResponsesCost: unreadable row %s", row.unified_object_id)
            return
        response_id: Final = str(row.unified_object_id)
        try:
            response: Final = await self._read_response(response_id, _owner_metadata(row))
        except Exception as e:
            provider_id: Final = _decoded_response_id(response_id).get("response_id") or response_id
            if (
                self._deployment_of(response_id) is not None
                and getattr(e, "status_code", None) == 404
                and provider_id in str(e)
            ):
                await self._set_status_if_pending(row, _STALE_RESPONSE_STATUS)
                return
            raise
        if str(getattr(response, "status", "")) in TERMINAL_RESPONSE_STATUSES:
            await self._bill(row, response)

    async def _set_status_if_pending(self, row: object, status: str) -> bool:
        claimed: Final = await self._table().update_many(
            where={"id": row.id, "status": {"in": list(_PENDING_RESPONSE_STATUSES)}}, data={"status": status}
        )
        return bool(claimed)

    async def _bill(self, row: object, response: object) -> _BilledCharge | None:
        if not await self._set_status_if_pending(row, "completed"):
            return None
        try:
            return await self._log_billing_event(row, response)
        except Exception:
            await self._table().update_many(where={"id": row.id, "status": "completed"}, data={"status": "queued"})
            raise

    async def _log_billing_event(self, row: object, response: object) -> _BilledCharge:
        response_id: Final = str(row.unified_object_id)
        decoded: Final = _decoded_response_id(response_id)
        deployment: Final = self._deployment_of(response_id)
        stored: Final = _row_file_object(row) or {}
        model: Final = str(getattr(response, "model", None) or stored.get("model") or "")
        deployment_params: Final = (
            deployment.hangarllm_params.model_dump(exclude_none=True) if deployment is not None else {}
        )
        now: Final = datetime.now(timezone.utc)
        logging_obj: Final = Logging(
            model=model,
            messages=[],
            stream=False,
            call_type="aget_responses",
            start_time=now,
            hangarllm_call_id=str(uuid.uuid4()),
            function_id="background_response_cost",
        )
        logging_obj.update_environment_variables(
            hangarllm_params={
                **{key: value for key, value in deployment_params.items() if key in _CUSTOM_PRICING_KEYS},
                "metadata": {
                    **_owner_metadata(row),
                    INTERNAL_CALL_ORIGIN_METADATA_KEY: BACKGROUND_RESPONSE_COST_POLL_CALL_ORIGIN,
                    **({"model_info": deployment.model_info.model_dump(exclude_none=True)} if deployment else {}),
                },
            },
            optional_params={},
            model=model,
            custom_llm_provider=decoded.get("custom_llm_provider") or "openai",
        )
        billed_response: Final = response.model_copy(update={"id": response_id})
        await logging_obj.async_success_handler(
            result=billed_response, start_time=now, end_time=datetime.now(timezone.utc), cache_hit=False
        )
        return _BilledCharge(cost=logging_obj.model_call_details.get("response_cost"), logging_obj=logging_obj)

    async def _tracked_row(self, response_id: str) -> object | None:
        return await self._table().find_first(where={"unified_object_id": response_id, "file_purpose": "response"})

    async def bill_from_deployment(
        self, response_id: str, track_untracked: Callable[[object], Awaitable[bool]] | None = None
    ) -> _BilledCharge | None:
        row: Final = await self._tracked_row(response_id)
        if row is None and track_untracked is None:
            return None
        if row is not None and row.status not in _PENDING_RESPONSE_STATUSES:
            return None
        if self._deployment_of(response_id) is None:
            return None
        response: Final = await self.llm_router.aget_responses(
            response_id=response_id,
            hangarllm_metadata={
                **(_owner_metadata(row) if row is not None else {}),
                INTERNAL_CALL_ORIGIN_METADATA_KEY: BACKGROUND_RESPONSE_STATUS_POLL_CALL_ORIGIN,
            },
        )
        return await self.bill_if_finished(response_id, response, track_untracked)

    async def bill_if_finished(
        self,
        response_id: str,
        response: object,
        track_untracked: Callable[[object], Awaitable[bool]] | None = None,
    ) -> _BilledCharge | None:
        if str(getattr(response, "status", "")) not in TERMINAL_RESPONSE_STATUSES:
            return None
        row: Final = await self._tracked_row(response_id)
        if row is not None:
            return await self._bill(row, response)
        if track_untracked is None or not await track_untracked(response):
            return None
        created: Final = await self._tracked_row(response_id)
        return await self._bill(created, response) if created is not None else None
