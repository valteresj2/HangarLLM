import logging
from typing import Final
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import hangarllm
from hangarllm._logging import verbose_logger
from hangarllm.proxy import proxy_server
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.proxy_server import app
from tests.unit.proxy.router_entry_point_stubs import route_entry_points_to_stubs

client = TestClient(app)


@pytest.fixture
def authenticated_client(monkeypatch):
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=HangarllmUserRoles.PROXY_ADMIN, api_key="sk-9876"
    )
    monkeypatch.setattr(
        hangarllm,
        "model_cost",
        {
            "sunset-model": {
                "deprecation_date": "2020-01-01",
                "hangarllm_provider": "openai",
            },
            "future-model": {
                "deprecation_date": "2099-01-01",
                "hangarllm_provider": "openai",
            },
        },
    )
    router = route_entry_points_to_stubs(MagicMock())
    router.get_model_list.return_value = [
        {
            "model_name": "sunset-alias",
            "hangarllm_params": {"model": "sunset-model"},
            "model_info": {"id": "1"},
        },
        {
            "model_name": "future-alias",
            "hangarllm_params": {"model": "future-model"},
            "model_info": {"id": "2"},
        },
    ]
    monkeypatch.setattr(proxy_server, "llm_router", router)
    yield client
    app.dependency_overrides.pop(user_api_key_auth, None)


def test_should_bucket_configured_models_by_urgency(authenticated_client):
    response = authenticated_client.get("/model/deprecations")

    assert response.status_code == 200
    payload = response.json()
    assert [m["model_name"] for m in payload["deprecated"]] == ["sunset-alias"]
    assert [m["model_name"] for m in payload["upcoming"]] == ["future-alias"]
    assert payload["imminent"] == []
    assert payload["warn_within_days"] == 30
    assert payload["deprecated"][0]["days_until_deprecation"] < 0


def test_should_rebucket_with_warn_within_days_override(authenticated_client):
    response = authenticated_client.get("/v1/model/deprecations", params={"warn_within_days": 40000})

    assert response.status_code == 200
    payload = response.json()
    assert [m["model_name"] for m in payload["imminent"]] == ["future-alias"]
    assert payload["upcoming"] == []
    assert payload["warn_within_days"] == 40000


@pytest.fixture
def client_with_cost_map_successors(monkeypatch):
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=HangarllmUserRoles.PROXY_ADMIN, api_key="sk-9876"
    )
    monkeypatch.setattr(
        hangarllm,
        "model_cost",
        {
            "retiring-model": {
                "deprecation_date": "2020-01-01",
                "hangarllm_provider": "openai",
                "successor_model": "fresh-model",
            },
            "orphan-model": {"deprecation_date": "2020-01-01", "hangarllm_provider": "openai"},
        },
    )
    router = route_entry_points_to_stubs(MagicMock())
    router.get_model_list.return_value = [
        {
            "model_name": "retiring-alias",
            "hangarllm_params": {"model": "retiring-model"},
            "model_info": {"id": "1"},
        },
        {
            "model_name": "retiring-overridden",
            "hangarllm_params": {"model": "retiring-model"},
            "model_info": {"id": "2", "successor_model": "my-own-pick"},
        },
        {
            "model_name": "shared-name",
            "hangarllm_params": {"model": "retiring-model", "api_key": "fake"},
            "model_info": {"id": "4"},
        },
        {
            "model_name": "shared-name",
            "hangarllm_params": {"model": "retiring-model", "api_key": "fake"},
            "model_info": {"id": "5", "successor_model": "my-own-pick"},
        },
        {
            "model_name": "dated-by-hand",
            "hangarllm_params": {"model": "retiring-model", "api_key": "fake"},
            "model_info": {"id": "6", "deprecation_date": "2020-06-01"},
        },
        {
            "model_name": "orphan-alias",
            "hangarllm_params": {"model": "orphan-model"},
            "model_info": {"id": "3"},
        },
    ]
    monkeypatch.setattr(proxy_server, "llm_router", router)
    yield client
    app.dependency_overrides.pop(user_api_key_auth, None)


def test_cost_map_successor_is_reported_unless_the_deployment_names_its_own(client_with_cost_map_successors):
    response = client_with_cost_map_successors.get("/model/deprecations")

    assert response.status_code == 200, response.text
    successors = {m["model_name"]: m["successor_model"] for m in response.json()["deprecated"]}
    assert successors == {
        "retiring-alias": "fresh-model",
        "retiring-overridden": "my-own-pick",
        "shared-name": "my-own-pick",
        "dated-by-hand": "fresh-model",
        "orphan-alias": None,
    }


def test_unmatched_successor_logs_below_warning_through_endpoint(client_with_cost_map_successors, caplog, monkeypatch):
    monkeypatch.setattr(
        proxy_server.llm_router.get_model_list,
        "side_effect",
        lambda model_name=None, **kwargs: (
            proxy_server.llm_router.get_model_list.return_value if model_name is None else []
        ),
    )

    with caplog.at_level(logging.DEBUG, logger=verbose_logger.name):
        response = client_with_cost_map_successors.get("/model/deprecations")

    assert response.status_code == 200, response.text
    successor_records = tuple(
        record
        for record in caplog.records
        if record.name == verbose_logger.name and "successor" in record.getMessage()
    )
    assert successor_records
    assert all(record.levelno < logging.WARNING for record in successor_records)


def test_mixed_successor_group_logs_below_warning_through_endpoint(
    client_with_cost_map_successors: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router: Final = proxy_server.llm_router
    models: Final[tuple[dict[str, object], ...]] = (
        {
            "model_name": "mixed-successor-group",
            "hangarllm_params": {"model": "retiring-model"},
            "model_info": {"id": "10", "successor_model": "successor-a"},
        },
        {
            "model_name": "mixed-successor-group",
            "hangarllm_params": {"model": "retiring-model"},
            "model_info": {"id": "11", "successor_model": "successor-b"},
        },
        {
            "model_name": "successor-a",
            "hangarllm_params": {"model": "fresh-model"},
            "model_info": {"id": "12"},
        },
        {
            "model_name": "successor-b",
            "hangarllm_params": {"model": "fresh-model"},
            "model_info": {"id": "13"},
        },
    )

    def filtered_model_list(
        model_name: str | None = None, **_kwargs: object
    ) -> tuple[dict[str, object], ...]:
        return models if model_name is None else tuple(model for model in models if model["model_name"] == model_name)

    monkeypatch.setattr(router.get_model_list, "side_effect", filtered_model_list)

    with caplog.at_level(logging.DEBUG, logger=verbose_logger.name):
        response = client_with_cost_map_successors.get("/model/deprecations")

    assert response.status_code == 200, response.text
    successor_records: Final = tuple(
        record
        for record in caplog.records
        if record.name == verbose_logger.name and "successor" in record.getMessage()
    )
    assert successor_records
    assert all(
        "names several successors" in record.getMessage() and record.levelno < logging.WARNING
        for record in successor_records
    )
