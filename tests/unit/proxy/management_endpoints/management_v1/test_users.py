"""The HTTP contract of `POST /management/v1/users/bulk`: envelope, problem documents and strict bodies.

The batching behaviour itself is covered next to the helper, in
`tests/unit/proxy/management_helpers/test_bulk_user_creation.py`, whose in-memory Prisma this reuses.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from hangarllm.proxy._types import HangarllmUserRoles, Member
from hangarllm.proxy.auth.user_api_key_auth import UserAPIKeyAuth, user_api_key_auth
from hangarllm.proxy.list_api.common import ManagementProblem, problem_response, request_validation_problem
from hangarllm.proxy.management_endpoints.management_v1 import router
from hangarllm.proxy.management_endpoints.management_v1.common import MANAGEMENT_V1_PREFIX
from tests.unit.proxy.management_helpers.test_bulk_user_creation import _FakePrisma, _License, _team

app = FastAPI()


@app.exception_handler(ManagementProblem)
async def management_problem_exception_handler(request: Request, exc: ManagementProblem):
    return problem_response(exc.problem)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return problem_response(request_validation_problem(exc.errors()))


app.include_router(router)
client = TestClient(app)

USERS_BULK_PATH = f"{MANAGEMENT_V1_PREFIX}/users/bulk"


@pytest.fixture
def as_proxy_admin():
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=HangarllmUserRoles.PROXY_ADMIN
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def prisma(monkeypatch):
    fake = _FakePrisma(teams=[_team("t1", [Member(user_id="existing", role="admin")])])
    monkeypatch.setattr("hangarllm.proxy.proxy_server.prisma_client", fake)
    monkeypatch.setattr("hangarllm.proxy.proxy_server._license_check", _License())
    return fake


def _post(body: object):
    return client.post(USERS_BULK_PATH, json=body, headers={"Authorization": "Bearer k"})


def test_returns_one_result_per_row_in_order_inside_the_data_meta_envelope(prisma, as_proxy_admin):
    response = _post(
        {
            "users": [
                {"user_id": "u1", "user_email": "a@example.com", "teams": ["t1"]},
                {"user_id": "u2", "teams": ["missing-team"]},
                {"user_id": "u3"},
            ]
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"] == {"total_requested": 3, "created": 2, "failed": 1}
    assert [row["user_id"] for row in body["data"]] == ["u1", "u2", "u3"]
    assert [row["success"] for row in body["data"]] == [True, False, True]
    assert body["data"][0]["teams"] == ["t1"]
    assert "missing-team" in body["data"][1]["error"]
    assert [m.user_id for m in prisma.db.hangarllm_teamtable.rows["t1"].members_with_roles] == ["existing", "u1"]


def test_an_unknown_field_anywhere_in_the_body_is_a_422_problem(prisma, as_proxy_admin):
    for body, field in (
        ({"users": [{"user_email": "a@example.com", "user_emial": "typo"}]}, "users.0.user_emial"),
        ({"users": [{"user_email": "a@example.com"}], "dry_run": True}, "dry_run"),
    ):
        response = _post(body)

        assert response.status_code == 422, body
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["type"] == "urn:hangarllm:error:invalid-request-body"
        assert response.json()["detail"] == f"{field}: Extra inputs are not permitted"
    assert prisma.db.hangarllm_usertable.rows == {}


def test_empty_and_oversized_batches_are_422_problems(prisma, as_proxy_admin):
    for users in ([], [{"user_email": f"{i}@example.com"} for i in range(501)]):
        response = _post({"users": users})

        assert response.status_code == 422, len(users)
        assert response.json()["type"] == "urn:hangarllm:error:invalid-request-body"
    assert prisma.db.hangarllm_usertable.rows == {}


def test_license_limit_is_a_403_problem_and_creates_nothing(prisma, as_proxy_admin, monkeypatch):
    monkeypatch.setattr("hangarllm.proxy.proxy_server._license_check", _License(max_users=1))

    response = _post({"users": [{"user_id": "u1"}, {"user_id": "u2"}]})

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "urn:hangarllm:error:license-limit-exceeded"
    assert prisma.db.hangarllm_usertable.rows == {}


def test_no_database_is_a_503_problem(as_proxy_admin, monkeypatch):
    monkeypatch.setattr("hangarllm.proxy.proxy_server.prisma_client", None)

    response = _post({"users": [{"user_id": "u1"}]})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "urn:hangarllm:error:database-not-connected"
