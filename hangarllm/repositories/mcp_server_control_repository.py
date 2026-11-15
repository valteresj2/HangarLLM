import json
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter, field_validator

from hangarllm.models.mcp_server_control import MCPServerControl
from hangarllm.types.llms.base import HangarLLMBaseModel

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient

_COLUMNS: Final = '"server_id", "disabled", "tool_overrides"'

LIST_CONTROLS_SQL: Final = f'SELECT {_COLUMNS} FROM "HangarLLM_MCPServerControlTable"'

SET_SERVER_DISABLED_SQL: Final = f"""
INSERT INTO "HangarLLM_MCPServerControlTable" ("server_id", "disabled", "tool_overrides", "updated_at", "updated_by")
VALUES ($1, $2, '{{}}'::jsonb, CURRENT_TIMESTAMP, $3)
ON CONFLICT ("server_id") DO UPDATE
SET "disabled" = EXCLUDED."disabled", "updated_at" = CURRENT_TIMESTAMP, "updated_by" = EXCLUDED."updated_by"
RETURNING {_COLUMNS}
"""

SET_TOOL_DISABLED_SQL: Final = f"""
INSERT INTO "HangarLLM_MCPServerControlTable" AS control
    ("server_id", "disabled", "tool_overrides", "updated_at", "updated_by")
VALUES ($1, false, jsonb_build_object($2::text, jsonb_build_object('disabled', $3::boolean)), CURRENT_TIMESTAMP, $4)
ON CONFLICT ("server_id") DO UPDATE
SET "tool_overrides" = control."tool_overrides" || jsonb_build_object(
        $2::text, COALESCE(control."tool_overrides" -> $2::text, '{{}}'::jsonb) || jsonb_build_object('disabled', $3::boolean)
    ),
    "updated_at" = CURRENT_TIMESTAMP,
    "updated_by" = EXCLUDED."updated_by"
RETURNING {_COLUMNS}
"""

DELETE_CONTROL_SQL: Final = 'DELETE FROM "HangarLLM_MCPServerControlTable" WHERE "server_id" = $1'


class _ToolOverride(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    disabled: bool = False


class _ControlRow(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    server_id: str
    disabled: bool
    tool_overrides: dict[str, _ToolOverride]

    @field_validator("tool_overrides", mode="before")
    @classmethod
    def _decode_json_text(cls, value: object) -> object:
        return json.loads(value) if isinstance(value, str) else value

    def as_control(self) -> MCPServerControl:
        return MCPServerControl(
            server_id=self.server_id,
            disabled=self.disabled,
            disabled_tools=frozenset(name for name, override in self.tool_overrides.items() if override.disabled),
        )


_ROWS: Final = TypeAdapter(tuple[_ControlRow, ...])


class MCPServerControlRepository:
    def __init__(self, prisma_client: "PrismaClient") -> None:
        self._prisma_client = prisma_client

    async def _query(self, sql: str, *params: object) -> tuple[MCPServerControl, ...]:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            sql, *params
        )
        return tuple(row.as_control() for row in _ROWS.validate_python(rows or ()))

    async def _upsert(self, sql: str, *params: object) -> MCPServerControl:
        rows: Final = await self._query(sql, *params)
        return rows[0]

    async def list_controls(self) -> tuple[MCPServerControl, ...]:
        return await self._query(LIST_CONTROLS_SQL)

    async def set_server_disabled(self, server_id: str, disabled: bool, updated_by: str) -> MCPServerControl:
        return await self._upsert(SET_SERVER_DISABLED_SQL, server_id, disabled, updated_by)

    async def set_tool_disabled(
        self, server_id: str, tool_name: str, disabled: bool, updated_by: str
    ) -> MCPServerControl:
        return await self._upsert(SET_TOOL_DISABLED_SQL, server_id, tool_name, disabled, updated_by)

    async def delete_control(self, server_id: str) -> None:
        await self._prisma_client.db.execute_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            DELETE_CONTROL_SQL, server_id
        )
