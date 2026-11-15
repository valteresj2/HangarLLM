import json
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter, field_validator

from hangarllm.models.mcp_server_control import MCPServerControl
from hangarllm.types.llms.base import HangarLLMBaseModel

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient

LIST_CONTROLS_SQL: Final = 'SELECT "server_id", "disabled", "tool_overrides" FROM "HangarLLM_MCPServerControlTable"'

SET_SERVER_DISABLED_SQL: Final = """
INSERT INTO "HangarLLM_MCPServerControlTable" ("server_id", "disabled", "tool_overrides", "updated_at", "updated_by")
VALUES ($1, $2, '{}'::jsonb, CURRENT_TIMESTAMP, $3)
ON CONFLICT ("server_id") DO UPDATE
SET "disabled" = EXCLUDED."disabled", "updated_at" = CURRENT_TIMESTAMP, "updated_by" = EXCLUDED."updated_by"
RETURNING "server_id", "disabled", "tool_overrides"
"""

SET_TOOL_DISABLED_SQL: Final = """
INSERT INTO "HangarLLM_MCPServerControlTable" AS control
    ("server_id", "disabled", "tool_overrides", "updated_at", "updated_by")
VALUES ($1, false, jsonb_build_object($2::text, jsonb_build_object('disabled', $3::boolean)), CURRENT_TIMESTAMP, $4)
ON CONFLICT ("server_id") DO UPDATE
SET "tool_overrides" = control."tool_overrides" || jsonb_build_object(
        $2::text, COALESCE(control."tool_overrides" -> $2::text, '{}'::jsonb) || jsonb_build_object('disabled', $3::boolean)
    ),
    "updated_at" = CURRENT_TIMESTAMP,
    "updated_by" = EXCLUDED."updated_by"
RETURNING "server_id", "disabled", "tool_overrides"
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


def _controls(rows: object) -> tuple[MCPServerControl, ...]:
    return tuple(row.as_control() for row in _ROWS.validate_python(rows or ()))


class MCPServerControlRepository:
    def __init__(self, prisma_client: "PrismaClient") -> None:
        self._prisma_client = prisma_client

    async def list_controls(self) -> tuple[MCPServerControl, ...]:
        return _controls(
            await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
                LIST_CONTROLS_SQL
            )
        )

    async def set_server_disabled(self, server_id: str, disabled: bool, updated_by: str) -> MCPServerControl:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            SET_SERVER_DISABLED_SQL, server_id, disabled, updated_by
        )
        return _controls(rows)[0]

    async def set_tool_disabled(
        self, server_id: str, tool_name: str, disabled: bool, updated_by: str
    ) -> MCPServerControl:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            SET_TOOL_DISABLED_SQL, server_id, tool_name, disabled, updated_by
        )
        return _controls(rows)[0]

    async def delete_control(self, server_id: str) -> None:
        await self._prisma_client.db.execute_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            DELETE_CONTROL_SQL, server_id
        )
