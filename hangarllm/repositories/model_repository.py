"""
Model repository for database operations on HangarLLM_ProxyModelTable.
"""

import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter

from hangarllm.models.model import HangarLLM_ProxyModelTable
from hangarllm.repositories.base_repository import BaseRepository, DbRecord, record_to_dict
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models

_HANGARLLM_PARAMS: Final = TypeAdapter(Mapping[str, object], config=ConfigDict(strict=True, hide_input_in_errors=True))


class _ProxyModelTableRepository(PrismaTableRepository["prisma_models.HangarLLM_ProxyModelTable"]):
    table_name = "hangarllm_proxymodeltable"


class ModelRepository(BaseRepository[HangarLLM_ProxyModelTable]):
    """Repository for proxy model database operations with encryption support."""

    def __init__(self, prisma_client: object, encryption_key: str | None = None) -> None:
        super().__init__(prisma_client)
        self._encryption_key = encryption_key

    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_ProxyModelTable"]:
        return _ProxyModelTableRepository(self._prisma_client).table

    @property
    def model_class(self) -> type[HangarLLM_ProxyModelTable]:
        return HangarLLM_ProxyModelTable

    def _encrypt_hangarllm_params(self, hangarllm_params: Mapping[str, object]) -> Mapping[str, object]:
        """Encrypt sensitive values in hangarllm_params."""
        from hangarllm.proxy.common_utils.encrypt_decrypt_utils import encrypt_value_helper

        encrypted: Final = {}
        for key, value in hangarllm_params.items():
            if isinstance(value, str):
                encrypted[key] = encrypt_value_helper(value, new_encryption_key=self._encryption_key)
            else:
                encrypted[key] = value
        return encrypted

    def _decrypt_hangarllm_params(self, hangarllm_params: Mapping[str, object]) -> Mapping[str, object]:
        """Decrypt sensitive values in hangarllm_params."""
        from hangarllm.proxy.common_utils.encrypt_decrypt_utils import decrypt_value_helper

        decrypted: Final = {}
        for key, value in hangarllm_params.items():
            if isinstance(value, str):
                decrypted[key] = decrypt_value_helper(
                    value, key=key, exception_type="debug", return_original_value=True
                )
            else:
                decrypted[key] = value
        return decrypted

    def _to_model(self, record: DbRecord | None) -> HangarLLM_ProxyModelTable | None:
        """Convert a database record to a Model with decryption."""
        if record is None:
            return None

        data: Final = dict(record_to_dict(record))

        hangarllm_params: Final = data.get("hangarllm_params")
        if isinstance(hangarllm_params, str):
            data["hangarllm_params"] = json.loads(hangarllm_params)
        model_info: Final = data.get("model_info")
        if isinstance(model_info, str):
            data["model_info"] = json.loads(model_info)

        if data.get("hangarllm_params"):
            data["hangarllm_params"] = self._decrypt_hangarllm_params(
                _HANGARLLM_PARAMS.validate_python(data["hangarllm_params"])
            )

        return HangarLLM_ProxyModelTable.model_validate(data)

    async def find_by_id(self, model_id: str, id_field: str = "model_id") -> HangarLLM_ProxyModelTable | None:
        return await super().find_by_id(model_id, id_field)

    async def find_by_name(self, model_name: str) -> list[HangarLLM_ProxyModelTable]:
        """Find models by name."""
        records: Final = await self.table.find_many(where={"model_name": model_name})
        return self._to_model_list(records)

    async def find_all(self) -> list[HangarLLM_ProxyModelTable]:
        """Find all models."""
        records: Final = await self.table.find_many()
        return self._to_model_list(records)

    async def find_unblocked(self) -> list[HangarLLM_ProxyModelTable]:
        """Find all models that are not blocked."""
        records: Final = await self.table.find_many(where={"blocked": False})
        return self._to_model_list(records)

    async def find_all_except(self, model_id: str) -> Sequence[HangarLLM_ProxyModelTable]:
        """Find every model except the row currently being updated."""
        records: Final = await self.table.find_many(where={"model_id": {"not": model_id}})
        return tuple(self._to_model_list(records))

    async def find_by_team_id(self, team_id: str) -> list[HangarLLM_ProxyModelTable]:
        """Find models associated with a specific team.

        Note: This filters in-memory since team_id is stored within hangarllm_params
        JSON. For large deployments with many models, consider adding a dedicated
        team_id column with a database index.
        """
        all_models: Final = await self.find_all()
        return [m for m in all_models if m.team_id == team_id]

    async def create_model(
        self,
        model_name: str,
        hangarllm_params: Mapping[str, object],
        created_by: str,
        model_id: str | None = None,
        model_info: Mapping[str, object] | None = None,
        blocked: bool = False,
    ) -> HangarLLM_ProxyModelTable:
        """Create a new model with encryption."""
        encrypted_params: Final = self._encrypt_hangarllm_params(hangarllm_params)

        data: Final[dict[str, str | bool]] = {
            "model_name": model_name,
            "hangarllm_params": json.dumps(encrypted_params),
            "created_by": created_by,
            "updated_by": created_by,
            "blocked": blocked,
        }
        if model_id is not None:
            data["model_id"] = model_id
        if model_info is not None:
            data["model_info"] = json.dumps(model_info)

        record: Final = await self.table.create(data=data)
        model: Final = self._to_model(record)
        assert model is not None
        return model

    async def update_model(
        self,
        model_id: str,
        updated_by: str,
        model_name: str | None = None,
        hangarllm_params: Mapping[str, object] | None = None,
        model_info: Mapping[str, object] | None = None,
        blocked: bool | None = None,
    ) -> HangarLLM_ProxyModelTable | None:
        """Update a model with encryption."""
        data: Final[dict[str, str | bool]] = {"updated_by": updated_by}
        if model_name is not None:
            data["model_name"] = model_name
        if hangarllm_params is not None:
            encrypted_params: Final = self._encrypt_hangarllm_params(hangarllm_params)
            data["hangarllm_params"] = json.dumps(encrypted_params)
        if model_info is not None:
            data["model_info"] = json.dumps(model_info)
        if blocked is not None:
            data["blocked"] = blocked

        record: Final = await self.table.update(where={"model_id": model_id}, data=data)
        return self._to_model(record)

    async def delete_model(self, model_id: str) -> HangarLLM_ProxyModelTable | None:
        """Delete a model."""
        return await self.delete(model_id, id_field="model_id")

    async def block_model(self, model_id: str, updated_by: str) -> HangarLLM_ProxyModelTable | None:
        """Block a model."""
        return await self.update_model(model_id, updated_by, blocked=True)

    async def unblock_model(self, model_id: str, updated_by: str) -> HangarLLM_ProxyModelTable | None:
        """Unblock a model."""
        return await self.update_model(model_id, updated_by, blocked=False)
