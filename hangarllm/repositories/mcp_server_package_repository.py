from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter

from hangarllm.mcp_runner.models import Launcher, PackageRef
from hangarllm.models.mcp_server_package import MCPServerPackage
from hangarllm.types.llms.base import HangarLLMBaseModel

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient

GET_PACKAGE_SQL: Final = """
SELECT "server_id", "launcher", "package_name", "package_version", "package_command", "package_lock",
       "egress_allow_hosts"
FROM "HangarLLM_MCPServerPackageTable"
WHERE "server_id" = $1
"""

SAVE_PACKAGE_SQL: Final = """
INSERT INTO "HangarLLM_MCPServerPackageTable"
    ("server_id", "launcher", "package_name", "package_version", "package_command", "package_lock",
     "egress_allow_hosts", "updated_at", "updated_by")
VALUES ($1, $2, $3, $4, $5, $6, $7::text[], CURRENT_TIMESTAMP, $8)
ON CONFLICT ("server_id") DO UPDATE
SET "launcher" = EXCLUDED."launcher",
    "package_name" = EXCLUDED."package_name",
    "package_version" = EXCLUDED."package_version",
    "package_command" = EXCLUDED."package_command",
    "package_lock" = EXCLUDED."package_lock",
    "egress_allow_hosts" = EXCLUDED."egress_allow_hosts",
    "updated_at" = CURRENT_TIMESTAMP,
    "updated_by" = EXCLUDED."updated_by"
RETURNING "server_id", "launcher", "package_name", "package_version", "package_command", "package_lock",
          "egress_allow_hosts"
"""


class _PackageRow(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    server_id: str
    launcher: Launcher
    package_name: str
    package_version: str
    package_command: str | None
    package_lock: str
    egress_allow_hosts: tuple[str, ...] | None

    def as_package(self) -> MCPServerPackage:
        return MCPServerPackage(
            server_id=self.server_id,
            package=PackageRef(
                launcher=self.launcher,
                name=self.package_name,
                version=self.package_version,
                command=self.package_command,
            ),
            lock=self.package_lock,
            egress_allow_hosts=self.egress_allow_hosts or (),
        )


_ROWS: Final = TypeAdapter(tuple[_PackageRow, ...])


class MCPServerPackageRepository:
    def __init__(self, prisma_client: "PrismaClient") -> None:
        self._prisma_client = prisma_client

    async def get_package(self, server_id: str) -> MCPServerPackage | None:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            GET_PACKAGE_SQL, server_id
        )
        parsed: Final = _ROWS.validate_python(rows or ())
        return parsed[0].as_package() if parsed else None

    async def save_package(self, package: MCPServerPackage, updated_by: str) -> MCPServerPackage:
        rows: Final = await self._prisma_client.db.query_raw(  # pyright: ignore[reportAny]  # untyped Prisma client
            SAVE_PACKAGE_SQL,
            package.server_id,
            package.package.launcher,
            package.package.name,
            package.package.version,
            package.package.command,
            package.lock,
            list(package.egress_allow_hosts),
            updated_by,
        )
        return _ROWS.validate_python(rows)[0].as_package()
