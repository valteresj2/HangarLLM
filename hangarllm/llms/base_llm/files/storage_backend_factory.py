"""
Factory for creating storage backend instances.

This module provides a factory function to instantiate the correct storage backend
based on the backend type. Backends use the same configuration as their corresponding
callbacks (e.g., azure_storage uses the same env vars as AzureBlobStorageLogger).
"""

from typing import TYPE_CHECKING

from hangarllm._logging import verbose_logger

from .azure_blob_storage_backend import AzureBlobStorageBackend
from .hangarllm_db_storage_backend import HANGARLLM_DB_STORAGE_BACKEND_NAME, HangarLLMDbStorageBackend
from .storage_backend import BaseFileStorageBackend

if TYPE_CHECKING:
    from hangarllm.proxy.utils import PrismaClient


def get_storage_backend(backend_type: str, prisma_client: "PrismaClient | None" = None) -> BaseFileStorageBackend:
    """
    Factory function to create a storage backend instance.

    Backends are configured using the same environment variables as their
    corresponding callbacks. For example, "azure_storage" uses the same
    env vars as AzureBlobStorageLogger. "hangarllm_db" stores file bytes in the
    proxy's own database and needs the connected Prisma client.

    Args:
        backend_type: Backend type identifier (e.g., "azure_storage", "hangarllm_db")
        prisma_client: The proxy's database client, required by "hangarllm_db"

    Returns:
        BaseFileStorageBackend: Instance of the appropriate storage backend

    Raises:
        ValueError: If backend_type is not supported, or "hangarllm_db" is asked for without a database
    """
    verbose_logger.debug("Creating storage backend: type=%s", backend_type)

    if backend_type == "azure_storage":
        return AzureBlobStorageBackend()
    if backend_type == HANGARLLM_DB_STORAGE_BACKEND_NAME:
        if prisma_client is None:
            raise ValueError(f"Storage backend {HANGARLLM_DB_STORAGE_BACKEND_NAME} requires a database-connected proxy")
        return HangarLLMDbStorageBackend(prisma_client)
    raise ValueError(
        f"Unsupported storage backend type: {backend_type}. "
        f"Supported types: azure_storage, {HANGARLLM_DB_STORAGE_BACKEND_NAME}"
    )
