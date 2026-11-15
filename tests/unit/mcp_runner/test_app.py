from pathlib import Path
from typing import Final

from fastapi.testclient import TestClient

from hangarllm.mcp_runner.app import RunnerSettings, build_app

TOKEN: Final = "t" * 40
KEY: Final = "a" * 64


def _client(tmp_path: Path) -> TestClient:
    settings: Final = RunnerSettings(
        token=TOKEN, data_dir=tmp_path, bwrap="/usr/bin/bwrap", npm="npm", uv="uv", python="/usr/bin/python3.13"
    )
    return TestClient(build_app(settings))


def test_the_instance_mcp_endpoint_reaches_the_session_bridge(tmp_path: Path):
    with _client(tmp_path) as client:
        response: Final = client.post(f"/v1/instances/{KEY}/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 404, response.text
    assert response.json() == {"error": "unknown instance"}


def test_every_runner_route_but_health_needs_the_token(tmp_path: Path):
    with _client(tmp_path) as client:
        responses: Final = {
            "mcp": client.post(f"/v1/instances/{KEY}/mcp", json={}).status_code,
            "list": client.get("/v1/instances").status_code,
            "stop": client.delete("/v1/servers/srv-1/instances").status_code,
            "wrong token": client.get("/v1/instances", headers={"Authorization": "Bearer nope"}).status_code,
            "health": client.get("/health").status_code,
        }

    assert responses == {"mcp": 401, "list": 401, "stop": 401, "wrong token": 401, "health": 200}


def test_an_instance_key_that_does_not_match_its_spec_is_refused(tmp_path: Path):
    spec: Final = {
        "server_id": "srv-1",
        "package": {"launcher": "npx", "name": "some-server", "version": "1.0.0"},
        "lock": "{}",
        "env": {"TOKEN": "alice"},
    }
    with _client(tmp_path) as client:
        response: Final = client.put(f"/v1/instances/{KEY}", json=spec, headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 400, response.text
