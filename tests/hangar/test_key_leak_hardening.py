import importlib.util
import sys
import types
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

from litellm._process_defaults import secret_file_values
from litellm.hangar.proxy.secret_separation import (
    SharedSecretError,
    enforce_secret_separation,
    shared_secret_problems,
)
from litellm.hangar.proxy.ui_session import (
    BROWSER_SESSION_KEY,
    SESSION_COOKIE,
    UiSessionMiddleware,
    browser_session_token,
    seal,
    session_claims,
    sign_session,
    unseal,
)
from litellm.proxy.auth.auth_utils import is_request_body_safe
from litellm.proxy.auth.login_utils import _matches_env_credentials, encode_ui_session_jwt, get_ui_credentials
from litellm.proxy.middleware.prometheus_auth_middleware import _presents_metrics_token

REAL_KEY = "sk-real-session-key"
SECRET = "unit-test-session-secret-0123456789abcdef"
MASTER = "sk-master-key-for-tests"


@pytest.fixture(autouse=True)
def _session_secret(monkeypatch):
    monkeypatch.setenv("LITELLM_UI_SESSION_SECRET", SECRET)
    monkeypatch.delenv("UI_PASSWORD", raising=False)
    monkeypatch.delenv("LITELLM_ALLOW_MASTER_KEY_UI_LOGIN", raising=False)


def _session_token(key: str = REAL_KEY) -> str:
    return sign_session({"user_id": "u1", "key": key, "user_role": "proxy_admin", "login_method": "sso", "exp": 4102444800})


async def _forwarded_scope(scope: dict) -> dict:
    seen = {}

    async def app(inner_scope, _receive, _send):
        seen.update(inner_scope)

    await UiSessionMiddleware(app)(scope, None, None)
    return seen


def _http_scope(headers: list[tuple[bytes, bytes]], kind: str = "http") -> dict:
    return {"type": kind, "headers": headers}


def _session_cookie(token: str | None = None) -> tuple[bytes, bytes]:
    return b"cookie", f"token=abc; {SESSION_COOKIE}={seal(token or _session_token())}".encode()


BEARER_PLACEHOLDER = (b"authorization", f"Bearer {BROWSER_SESSION_KEY}".encode())


class TestBrowserNeverHoldsTheKey:
    def test_browser_token_keeps_claims_but_replaces_the_key(self):
        claims = jwt.decode(browser_session_token(_session_token()), options={"verify_signature": False})
        assert claims["key"] == BROWSER_SESSION_KEY and claims["user_role"] == "proxy_admin"

    def test_session_is_signed_with_its_own_secret_not_the_master_key(self):
        token = encode_ui_session_jwt({"user_id": "u1", "key": REAL_KEY})
        assert jwt.decode(token, SECRET, algorithms=["HS256"])["key"] == REAL_KEY
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, MASTER, algorithms=["HS256"])

    def test_sealed_cookie_is_opaque_and_tamper_evident(self):
        token = _session_token()
        sealed = seal(token)
        assert REAL_KEY not in sealed and "eyJ" not in sealed
        assert unseal(sealed) == token
        flipped = ("A" if sealed[20] != "A" else "B").join((sealed[:20], sealed[21:]))
        assert unseal(flipped) is None

    @pytest.mark.parametrize("length", range(6))
    def test_sealed_value_never_needs_cookie_quoting(self, length):
        sealed = seal("x" * length)
        assert "=" not in sealed
        assert unseal(sealed) == "x" * length

    def test_session_claims_rejects_expired_sessions(self):
        expired = sign_session({"key": REAL_KEY, "exp": 1})
        assert session_claims({SESSION_COOKIE: seal(expired)}) is None
        assert session_claims({SESSION_COOKIE: seal(_session_token())})["key"] == REAL_KEY


class TestMiddleware:
    @pytest.mark.asyncio
    async def test_placeholder_becomes_the_real_key(self):
        scope = await _forwarded_scope(_http_scope([BEARER_PLACEHOLDER, _session_cookie()]))
        assert dict(scope["headers"])[b"authorization"] == f"Bearer {REAL_KEY}".encode()

    @pytest.mark.asyncio
    async def test_cross_site_requests_do_not_get_the_session(self):
        scope = await _forwarded_scope(_http_scope([BEARER_PLACEHOLDER, _session_cookie(), (b"sec-fetch-site", b"cross-site")]))
        assert dict(scope["headers"])[b"authorization"] == BEARER_PLACEHOLDER[1]

    @pytest.mark.asyncio
    async def test_forged_cookie_leaves_the_placeholder_to_fail_auth(self):
        forged = (b"cookie", f"{SESSION_COOKIE}=not-a-real-seal".encode())
        scope = await _forwarded_scope(_http_scope([BEARER_PLACEHOLDER, forged]))
        assert dict(scope["headers"])[b"authorization"] == BEARER_PLACEHOLDER[1]

    @pytest.mark.asyncio
    async def test_real_api_keys_pass_through_untouched(self):
        headers = [(b"authorization", b"Bearer sk-from-a-script"), _session_cookie()]
        scope = await _forwarded_scope(_http_scope(headers))
        assert scope["headers"] == headers

    @pytest.mark.asyncio
    async def test_websocket_key_never_reaches_the_echoed_subprotocol(self):
        protocol = (b"sec-websocket-protocol", f"realtime, openai-insecure-api-key.{BROWSER_SESSION_KEY}".encode())
        scope = await _forwarded_scope(_http_scope([protocol, _session_cookie()], kind="websocket"))
        headers = dict(scope["headers"])
        assert headers[b"authorization"] == f"Bearer {REAL_KEY}".encode()
        assert REAL_KEY.encode() not in headers[b"sec-websocket-protocol"]


class TestUiLoginCredentials:
    def test_master_key_is_not_a_ui_password_by_default(self):
        with pytest.raises(Exception, match="UI_PASSWORD"):
            get_ui_credentials(MASTER)
        assert not _matches_env_credentials("admin", MASTER, MASTER)

    def test_ui_password_logs_in(self, monkeypatch):
        monkeypatch.setenv("UI_PASSWORD", "a-distinct-password")
        assert _matches_env_credentials("admin", "a-distinct-password", MASTER)
        assert not _matches_env_credentials("admin", MASTER, MASTER)

    def test_explicit_opt_in_restores_master_key_login(self, monkeypatch):
        monkeypatch.setenv("LITELLM_ALLOW_MASTER_KEY_UI_LOGIN", "true")
        assert _matches_env_credentials("admin", MASTER, MASTER)


class TestSecretSeparation:
    def _problems(self, **overrides):
        values = {
            "master_key": MASTER,
            "salt_key": "salt",
            "ui_password": "pw",
            "session_secret": None,
            "database_is_configured": True,
        }
        return shared_secret_problems(**{**values, **overrides})

    def test_distinct_secrets_pass(self):
        assert self._problems() == ()

    @pytest.mark.parametrize(
        ("overrides", "fragment"),
        [
            ({"salt_key": None}, "is not set"),
            ({"salt_key": MASTER}, "LITELLM_SALT_KEY is the same"),
            ({"ui_password": MASTER}, "UI_PASSWORD"),
            ({"session_secret": MASTER}, "LITELLM_UI_SESSION_SECRET"),
        ],
    )
    def test_each_shared_secret_is_reported(self, overrides, fragment):
        (problem,) = self._problems(**overrides)
        assert fragment in problem

    def test_missing_salt_is_fine_without_a_database(self):
        assert self._problems(salt_key=None, database_is_configured=False) == ()

    def test_boot_stops_unless_explicitly_allowed(self):
        announced = []
        with pytest.raises(SharedSecretError):
            enforce_secret_separation(
                master_key=MASTER, database_is_configured=True, announce=announced.append, environ={}
            )
        assert "LITELLM_SALT_KEY" in announced[0] and MASTER not in announced[0]
        enforce_secret_separation(
            master_key=MASTER,
            database_is_configured=True,
            announce=announced.append,
            environ={"LITELLM_ALLOW_SHARED_SECRETS": "true"},
        )


class TestSecretFiles:
    def test_file_value_is_read_and_stripped(self, tmp_path):
        secret = tmp_path / "master"
        secret.write_text("sk-from-file\n")
        assert secret_file_values({"HANGARLLM_MASTER_KEY_FILE": str(secret)}) == {"HANGARLLM_MASTER_KEY": "sk-from-file"}

    def test_explicit_value_wins_but_empty_one_does_not(self, tmp_path):
        secret = tmp_path / "pw"
        secret.write_text("from-file")
        assert secret_file_values({"UI_PASSWORD": "explicit", "UI_PASSWORD_FILE": str(secret)}) == {}
        assert secret_file_values({"UI_PASSWORD": "", "UI_PASSWORD_FILE": str(secret)}) == {"UI_PASSWORD": "from-file"}

    def test_only_allowlisted_variables_are_expanded(self, tmp_path):
        ignored = tmp_path / "cert"
        ignored.write_text("x")
        assert secret_file_values({"SSL_CERT_FILE": str(ignored), "SSL_CERT": ""}) == {}

    def test_unreadable_file_stops_startup_with_the_variable_name(self):
        with pytest.raises(RuntimeError, match="UI_PASSWORD_FILE"):
            secret_file_values({"UI_PASSWORD_FILE": "/nonexistent/secret"})


class TestClientCredentialParams:
    ROUTE = "/v1/chat/completions"

    def _check(self, body, settings=None, route=ROUTE):
        return is_request_body_safe(body, settings or {}, None, "gpt", route=route)

    @pytest.mark.parametrize("param", ["api_key", "extra_headers"])
    def test_llm_routes_reject_caller_supplied_credentials(self, param):
        with pytest.raises((ValueError, HTTPException), match=param):
            self._check({"model": "gpt", param: "x"})

    def test_nested_extra_body_is_also_rejected(self):
        with pytest.raises((ValueError, HTTPException), match="api_key"):
            self._check({"model": "gpt", "extra_body": {"api_key": "x"}})

    def test_admin_opt_in_allows_them(self):
        assert self._check({"model": "gpt", "api_key": "x"}, {"allow_client_side_credentials": True})

    def test_management_routes_keep_their_own_api_key_fields(self):
        assert self._check({"api_key": "hashed"}, route="/spend/logs")


class TestMetricsToken:
    def _scope(self, value: bytes) -> dict:
        return {"headers": [(b"authorization", value)]}

    def test_only_the_exact_token_is_accepted(self, monkeypatch):
        monkeypatch.setenv("LITELLM_METRICS_TOKEN", "scrape-me")
        assert _presents_metrics_token(self._scope(b"Bearer scrape-me"))
        assert not _presents_metrics_token(self._scope(b"Bearer wrong"))

    def test_disabled_when_unset(self, monkeypatch):
        monkeypatch.delenv("LITELLM_METRICS_TOKEN", raising=False)
        assert not _presents_metrics_token(self._scope(b"Bearer "))


class _FakeSession:
    captured: dict = {}

    def __init__(self, **kwargs):
        type(self).captured = kwargs

    def __enter__(self):
        raise RuntimeError("stop after capturing the session options")

    def __exit__(self, *_exc):
        return False


class TestSkillSandbox:
    @pytest.fixture(autouse=True)
    def _fake_llm_sandbox(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "llm_sandbox", types.SimpleNamespace(SandboxSession=_FakeSession))
        monkeypatch.delenv("HANGARLLM_SKILL_SANDBOX_NETWORK", raising=False)
        _FakeSession.captured = {}

    def _execute(self, skill_files=None):
        from litellm.llms.litellm_proxy.skills.sandbox_executor import SkillsSandboxExecutor

        return SkillsSandboxExecutor().execute(code="print(1)", skill_files=skill_files or {})

    def test_sandbox_has_no_network_env_or_privileges_by_default(self):
        self._execute()
        runtime = _FakeSession.captured["runtime_configs"]
        assert runtime["network_mode"] == "none" and runtime["environment"] == {}
        assert runtime["cap_drop"] == ["ALL"] and "no-new-privileges" in runtime["security_opt"]
        assert _FakeSession.captured["skip_environment_setup"] is True

    def test_package_installs_are_refused_without_network(self):
        result = self._execute({"requirements.txt": b"requests"})
        assert not result["success"] and "HANGARLLM_SKILL_SANDBOX_NETWORK" in result["error"]
        assert _FakeSession.captured == {}

    def test_operator_can_allow_network(self, monkeypatch):
        monkeypatch.setenv("HANGARLLM_SKILL_SANDBOX_NETWORK", "true")
        self._execute({"requirements.txt": b"requests"})
        assert "network_mode" not in _FakeSession.captured["runtime_configs"]
        assert _FakeSession.captured["runtime_configs"]["cap_drop"] == ["ALL"]


def _init_secrets_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "hangar_init_secrets.py"
    spec = importlib.util.spec_from_file_location("hangar_init_secrets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestInitSecrets:
    def _run(self, monkeypatch, tmp_path):
        module = _init_secrets_module()
        monkeypatch.setattr(sys, "argv", ["x", "--dir", str(tmp_path / "secrets"), "--env-file", str(tmp_path / ".env")])
        module.main()

    def test_env_secrets_move_to_files_and_other_settings_stay(self, monkeypatch, tmp_path, capsys):
        (tmp_path / ".env").write_text('HANGARLLM_MASTER_KEY="sk-old"\nHANGARLLM_SALT_KEY = "old-salt"\nOPENAI_API_KEY=keep\n')
        self._run(monkeypatch, tmp_path)
        assert (tmp_path / "secrets" / "master_key").read_text() == "sk-old"
        assert (tmp_path / "secrets" / "salt_key").read_text() == "old-salt"
        assert (tmp_path / ".env").read_text() == "OPENAI_API_KEY=keep\n"
        assert "sk-old" not in capsys.readouterr().out

    def test_rerun_never_rotates_the_salt_key(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path)
        first = (tmp_path / "secrets" / "salt_key").read_text()
        self._run(monkeypatch, tmp_path)
        assert (tmp_path / "secrets" / "salt_key").read_text() == first

    def test_every_secret_is_distinct_and_the_database_url_uses_the_password(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path)
        secrets_dir = tmp_path / "secrets"
        generated = [p.read_text() for p in secrets_dir.iterdir() if p.name != "database_url"]
        assert len(set(generated)) == len(generated) == 7
        assert (secrets_dir / "postgres_password").read_text() in (secrets_dir / "database_url").read_text()
