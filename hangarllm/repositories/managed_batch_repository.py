from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from hangarllm.repositories.table_repositories import PrismaTableRepository
from hangarllm.types.utils import HangarLLMBatch

if TYPE_CHECKING:
    from prisma import models as prisma_models


def _batch_of(blob: object) -> HangarLLMBatch:
    return HangarLLMBatch.model_validate_json(blob) if isinstance(blob, str) else HangarLLMBatch.model_validate(blob)


class ManagedBatchRepository(PrismaTableRepository["prisma_models.HangarLLM_ManagedObjectTable"]):
    table_name = "hangarllm_managedobjecttable"

    async def load_batch(self, unified_batch_id: str) -> HangarLLMBatch | None:
        row: Final = await self._find_row(unified_batch_id)
        return None if row is None or not row.file_object else _batch_of(row.file_object)

    async def load_status(self, unified_batch_id: str) -> str | None:
        row: Final = await self._find_row(unified_batch_id)
        return row.status if row is not None else None

    async def compare_and_set(
        self, batch: HangarLLMBatch, unchanged: Mapping[str, object], updated_by: str | None
    ) -> bool:
        updated_rows: Final = await self.table.update_many(
            where={"unified_object_id": batch.id, **unchanged},
            data={
                "file_object": batch.model_dump_json(),
                "status": batch.status,
                "updated_by": updated_by,
            },
        )
        return updated_rows > 0

    async def touch(self, unified_batch_id: str, updated_by: str | None) -> None:
        await self.table.update_many(
            where={"unified_object_id": unified_batch_id},
            data={"updated_by": updated_by},
        )

    async def _find_row(self, unified_batch_id: str) -> "prisma_models.HangarLLM_ManagedObjectTable | None":
        return await self.table.find_first(where={"unified_object_id": unified_batch_id})
