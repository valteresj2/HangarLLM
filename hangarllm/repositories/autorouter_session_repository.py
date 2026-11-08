"""
Repository for the auto-router per-session rollup (HangarLLM_AutoRouterSession).
"""

from typing import TYPE_CHECKING, Final

from hangarllm.models.autorouter_session import HangarLLM_AutoRouterSession
from hangarllm.repositories.base_repository import BaseRepository
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models


class _AutoRouterSessionTable(PrismaTableRepository["prisma_models.HangarLLM_AutoRouterSession"]):
    table_name = "hangarllm_autoroutersession"


class AutoRouterSessionRepository(BaseRepository[HangarLLM_AutoRouterSession]):
    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_AutoRouterSession"]:
        return _AutoRouterSessionTable(self._prisma_client).table

    @property
    def model_class(self) -> type[HangarLLM_AutoRouterSession]:
        return HangarLLM_AutoRouterSession

    async def find_latest_for_key(self, api_key: str, session_id: str) -> HangarLLM_AutoRouterSession | None:
        """The session's most recently active router row under exactly this key hash, or None.

        The key is the row's own partition, not a filter over a wider read: the spend writer keyed the
        row under the caller's api_key, so a key can only ever see what it wrote itself.
        """
        record: Final = await self.table.find_first(
            where={"api_key": api_key, "session_id": session_id},
            order={"last_turn_at": "desc"},
        )
        return self._to_model(record)
