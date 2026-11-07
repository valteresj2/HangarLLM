"""
Background cost reconciliation.

``CheckBatchCost``
    Every ``PROXY_BATCH_POLLING_INTERVAL`` seconds, finds managed batches whose
    cost has not been accounted yet, re-reads them from the deployment that runs
    them and - once a batch reaches a final state - lets core's logging pipeline
    price the output file and write the spend log under the original key / team /
    org / tags. The batch is then marked ``batch_processed`` so it is billed once.

``CheckResponsesCost``
    Tracks background (``background: true``) Responses API calls stored as
    managed objects and retires them once they reach a terminal status. Billing of
    background responses happens on the create/stream path; the poller keeps the
    table bounded and exposes the ``bill_*`` hooks the responses endpoint calls.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Final

from litellm._logging import verbose_proxy_logger

GIVE_UP_POLLING_AFTER: Final = timedelta(days=7)
_PAGE_SIZE: Final = 50
_TERMINAL_BATCH_STATUSES: Final = frozenset({"completed", "complete", "failed", "cancelled", "expired"})
_TERMINAL_RESPONSE_STATUSES: Final = frozenset({"completed", "failed", "cancelled", "incomplete"})


def _decoded(unified_id: str) -> str | None:
    from litellm.proxy.openai_files_endpoints.common_utils import is_base64_encoded_unified_file_id

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
        from litellm.repositories.table_repositories import ManagedObjectRepository

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
        from litellm.proxy.openai_files_endpoints.common_utils import (
            get_batch_id_from_unified_batch_id,
            get_model_id_from_unified_batch_id,
            is_litellm_executed_batch,
        )

        unified_id: Final = str(row.unified_object_id)
        decoded: Final = _decoded(unified_id)
        if decoded is None or is_litellm_executed_batch(decoded):
            return  # gateway-executed batches bill themselves
        model_id: Final = get_model_id_from_unified_batch_id(decoded)
        provider_batch_id: Final = get_batch_id_from_unified_batch_id(decoded)
        if not model_id or not provider_batch_id:
            return
        batch: Final = await self.llm_router.aretrieve_batch(
            model=model_id,
            batch_id=provider_batch_id,
            litellm_metadata={**_owner_metadata(row), "model_group": model_id},
        )
        status: Final = str(getattr(batch, "status", "") or "")
        update: dict[str, object] = {  # mutable-ok: prisma payload
            "status": "complete" if status == "completed" else status,
            "file_object": batch.model_dump_json(),
        }
        if status in _TERMINAL_BATCH_STATUSES:
            from litellm.litellm_core_utils.batch_utils import batch_cost_is_final

            final: Final = status != "completed" or batch_cost_is_final(batch)
            if final and not self._column_absent:
                update["batch_processed"] = True
        await self._table().update(where={"unified_object_id": unified_id}, data=update)


class CheckResponsesCost:
    def __init__(self, proxy_logging_obj, prisma_client, llm_router) -> None:
        self.proxy_logging_obj = proxy_logging_obj
        self.prisma_client = prisma_client
        self.llm_router = llm_router

    def _table(self):
        from litellm.repositories.table_repositories import ManagedObjectRepository

        return ManagedObjectRepository(self.prisma_client).table

    async def check_responses_cost(self) -> None:
        if self.prisma_client is None:
            return
        cutoff: Final = datetime.now(timezone.utc) - GIVE_UP_POLLING_AFTER
        try:
            rows = await self._table().find_many(
                where={"file_purpose": "response", "batch_processed": False, "created_at": {"gte": cutoff}},
                take=_PAGE_SIZE,
            )
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.debug("HangarLLM CheckResponsesCost: query failed - %s", e)
            return
        for row in rows:
            status = str(getattr(row, "status", "") or "")
            if status in _TERMINAL_RESPONSE_STATUSES:
                try:
                    await self._table().update(
                        where={"unified_object_id": row.unified_object_id}, data={"batch_processed": True}
                    )
                except Exception as e:  # noqa: BLE001
                    verbose_proxy_logger.debug("HangarLLM CheckResponsesCost: update failed - %s", e)

    async def bill_from_deployment(
        self, response_id: str, track_untracked: Callable[[object], Awaitable[bool]] | None = None
    ) -> None:
        return None

    async def bill_if_finished(
        self,
        response_id: str,
        response: object,
        track_untracked: Callable[[object], Awaitable[bool]] | None = None,
    ) -> None:
        if track_untracked is not None:
            try:
                await track_untracked(response)
            except Exception as e:  # noqa: BLE001
                verbose_proxy_logger.debug("HangarLLM: could not track background response %s - %s", response_id, e)
