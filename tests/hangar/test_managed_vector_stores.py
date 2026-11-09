import base64
from collections.abc import Mapping
from typing import Final

import pytest
from fastapi import HTTPException

from hangarllm.hangar.proxy.managed_vector_stores import HangarManagedVectorStores
from hangarllm.proxy._types import UserAPIKeyAuth

_STORE_ID: Final = (
    base64.urlsafe_b64encode(
        b"hangarllm_proxy:vector_store;unified_id,uuid-1;model_id,deployment-1;provider_resource_id,vs_provider"
    )
    .decode()
    .rstrip("=")
)
_OWNED_BY_TEAM_A: Final = {"created_by": "alice", "team_id": "team-a"}


class _Cache:
    def __init__(self, resources: Mapping[str, Mapping[str, object]]) -> None:
        self._resources: Final = resources

    async def async_get_cache(self, key: str, hangarllm_parent_otel_span: object = None) -> object:
        return self._resources.get(key)


class _NoRows:
    def __getattr__(self, name: str) -> "_NoRows":
        return self

    async def find_first(self, where: Mapping[str, object]) -> None:
        return None


def _hook(resources: Mapping[str, Mapping[str, object]]) -> HangarManagedVectorStores:
    return HangarManagedVectorStores(internal_usage_cache=_Cache(resources), prisma_client=_NoRows())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call_type", ["avector_store_search", "avector_store_retrieve", "avector_store_update", "avector_store_delete"]
)
async def test_another_teams_key_cannot_reach_a_managed_store(call_type: str) -> None:
    hook: Final = _hook({_STORE_ID: _OWNED_BY_TEAM_A})

    with pytest.raises(HTTPException) as rejected:
        await hook.async_pre_call_hook(
            UserAPIKeyAuth(user_id="mallory", team_id="team-b"), None, {"vector_store_id": _STORE_ID}, call_type
        )

    assert rejected.value.status_code == 403


@pytest.mark.asyncio
async def test_the_owner_is_routed_to_the_provider_store_on_its_deployment() -> None:
    hook: Final = _hook({_STORE_ID: _OWNED_BY_TEAM_A})

    data: Final = await hook.async_pre_call_hook(
        UserAPIKeyAuth(user_id="alice", team_id="team-a"),
        None,
        {"vector_store_id": _STORE_ID, "query": "q"},
        "avector_store_search",
    )

    assert data == {"model": "deployment-1", "vector_store_id": "vs_provider", "query": "q"}


@pytest.mark.asyncio
async def test_a_unified_id_with_no_stored_owner_is_refused() -> None:
    with pytest.raises(HTTPException) as rejected:
        await _hook({}).async_pre_call_hook(
            UserAPIKeyAuth(user_id="mallory", team_id="team-b"),
            None,
            {"vector_store_id": _STORE_ID},
            "avector_store_retrieve",
        )

    assert rejected.value.status_code == 403


@pytest.mark.asyncio
async def test_a_provider_native_id_passes_through_unchanged() -> None:
    request: Final = {"vector_store_id": "vs_native"}

    data: Final = await _hook({}).async_pre_call_hook(
        UserAPIKeyAuth(user_id="alice"), None, request, "avector_store_search"
    )

    assert data is request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resources", "user_id", "team_id", "denied"),
    [
        ({_STORE_ID: _OWNED_BY_TEAM_A}, "mallory", "team-b", True),
        ({_STORE_ID: _OWNED_BY_TEAM_A}, "alice", "team-a", False),
        ({}, "mallory", "team-b", False),
    ],
)
async def test_denies_access_only_for_a_stored_store_the_caller_does_not_own(
    resources: Mapping[str, Mapping[str, object]], user_id: str, team_id: str, denied: bool
) -> None:
    result: Final = await _hook(resources).denies_access(_STORE_ID, UserAPIKeyAuth(user_id=user_id, team_id=team_id))

    assert result is denied
