from typing import TYPE_CHECKING, Final

from hangarllm.llms.base_llm.files.storage_backend import BaseFileStorageBackend
from hangarllm.repositories.managed_file_content_repository import ManagedFileContentRepository

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient

HANGARLLM_DB_STORAGE_BACKEND_NAME: Final = "hangarllm_db"
HANGARLLM_DB_STORAGE_URL_PREFIX: Final = f"{HANGARLLM_DB_STORAGE_BACKEND_NAME}://"


def storage_url_to_row_id(storage_url: str) -> str:
    if not storage_url.startswith(HANGARLLM_DB_STORAGE_URL_PREFIX):
        raise ValueError(f"Not a {HANGARLLM_DB_STORAGE_BACKEND_NAME} storage url: {storage_url}")
    return storage_url.removeprefix(HANGARLLM_DB_STORAGE_URL_PREFIX)


class HangarLLMDbStorageBackend(BaseFileStorageBackend):
    def __init__(self, prisma_client: "PrismaClient") -> None:
        self._contents = ManagedFileContentRepository(prisma_client)

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        path_prefix: str | None = None,
        file_naming_strategy: str = "uuid",
    ) -> str:
        return f"{HANGARLLM_DB_STORAGE_URL_PREFIX}{await self._contents.store(file_content)}"

    async def download_file(self, storage_url: str) -> bytes:
        content: Final = await self._contents.load(storage_url_to_row_id(storage_url))
        if content is None:
            raise ValueError(f"No stored file content for {storage_url}")
        return content

    async def delete_file(self, storage_url: str) -> None:
        await self._contents.delete(storage_url_to_row_id(storage_url))
