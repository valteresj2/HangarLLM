"""Unit tests for the open-core HangarLLM extensions (hangarllm.hangar)."""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from fastapi import HTTPException

import hangarllm
from hangarllm.caching.dual_cache import DualCache
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth


# --------------------------------------------------------------------------- callback controls
class TestCallbackControls:
    def _check(self, callback, headers=None, dynamic=None):
        from hangarllm.hangar.callbacks.callback_controls import HangarCallbackControls

        params = {"proxy_server_request": {"headers": headers or {}}}
        return HangarCallbackControls.is_callback_disabled_dynamically(callback, params, dynamic or {})

    def test_header_disables_named_callback_case_insensitive(self):
        assert self._check("langfuse", {"x-hangarllm-disable-callbacks": " LangFuse , datadog"}) is True
        assert self._check("datadog", {"x-hangarllm-disable-callbacks": "langfuse,datadog"}) is True
        assert self._check("s3_v2", {"x-hangarllm-disable-callbacks": "langfuse"}) is False

    def test_hangar_header_alias(self):
        assert self._check("langfuse", {"x-hangarllm-disable-callbacks": "langfuse"}) is True

    def test_body_list(self):
        assert self._check("langfuse", dynamic={"hangarllm_disabled_callbacks": ["Langfuse"]}) is True
        assert self._check("datadog", dynamic={"hangarllm_disabled_callbacks": ["langfuse"]}) is False

    def test_operator_can_turn_off(self, monkeypatch):
        monkeypatch.setattr(hangarllm, "allow_dynamic_callback_disabling", False)
        assert self._check("langfuse", {"x-hangarllm-disable-callbacks": "langfuse"}) is False

    def test_logger_instance_matched_through_registry(self):
        from hangarllm.integrations.custom_logger import CustomLogger
        from hangarllm.hangarllm_core_utils.custom_logger_registry import CustomLoggerRegistry

        class MyLogger(CustomLogger):
            pass

        with patch.dict(CustomLoggerRegistry.CALLBACK_CLASS_STR_TO_CLASS_TYPE, {"my_logger": MyLogger}):
            assert self._check(MyLogger(), {"x-hangarllm-disable-callbacks": "my_logger"}) is True
            assert self._check(MyLogger(), {"x-hangarllm-disable-callbacks": "other"}) is False


# --------------------------------------------------------------------------- payload enrichment
def test_custom_headers_logged_without_credentials():
    from hangarllm.hangar.callbacks.logging_payload import HangarLoggingPayloadSetup

    metadata = {}
    out = HangarLoggingPayloadSetup.apply_enterprise_specific_metadata(
        metadata,
        {
            "headers": {
                "X-Request-Source": "billing-svc",
                "x-api-key": "secret",
                "x-hangarllm-api-key": "sk-1",
                "x-session-token": "t",
                "content-type": "application/json",
            }
        },
    )
    assert out["requester_custom_headers"] == {"x-request-source": "billing-svc"}


# --------------------------------------------------------------------------- secret detection
class TestSecretDetection:
    def _g(self, **kwargs):
        from hangarllm.hangar.guardrails.secret_detection import HangarSecretDetection

        return HangarSecretDetection(**kwargs)

    @pytest.mark.parametrize(
        "secret",
        [
            "AKIAIOSFODNN7EXAMPLE",
            "ghp_" + "a" * 36,
            "xoxb-123456789012-abcdefghijkl",
            "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc",
            "AIza" + "S" * 35,
            "hf_" + "B" * 34,
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
        ],
    )
    def test_known_formats_redacted(self, secret):
        g = self._g()
        out = g.redact_text(f"here it is: {secret} ok")
        assert secret not in out and "[REDACTED]" in out and out.endswith(" ok")

    def test_credential_assignments(self):
        g = self._g()
        assert g.redact_text("DB_PASSWORD=hunter2brahms9x systemctl") == "DB_PASSWORD=[REDACTED] systemctl"
        assert g.redact_text('{"client_secret": "abcdef123456"}') == '{"client_secret": "[REDACTED]"}'

    def test_placeholders_and_plain_text_kept(self):
        g = self._g()
        for text in ("password=${DB_PASSWORD}", "api_key: <your-key>", "The quick brown fox", "token = null"):
            assert g.scan_message_for_secrets(text) == []

    def test_tool_payload_keeps_keys(self):
        g = self._g()
        out = g.redact_tool_payload({"password": "hunter2brahms9x", "command": "export API_TOKEN=zzzzzzzz1", "n": 3})
        assert out == {"password": "[REDACTED]", "command": "export API_TOKEN=[REDACTED]", "n": 3}

    def test_disabled_and_custom_patterns(self):
        g = self._g(detect_secrets_config={"disabled_patterns": ["aws_access_key_id"], "custom_patterns": {"itk": r"itk_[a-z]{8}"}})
        assert g.redact_text("AKIAIOSFODNN7EXAMPLE") == "AKIAIOSFODNN7EXAMPLE"
        assert g.redact_text("use itk_abcdefgh") == "use [REDACTED]"

    @pytest.mark.asyncio
    async def test_pre_call_hook_redacts_messages_and_tool_args(self):
        g = self._g()
        data = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "key AKIAIOSFODNN7EXAMPLE"}]},
                {
                    "role": "assistant",
                    "tool_calls": [{"function": {"name": "f", "arguments": '{"password": "hunter2brahms9x"}'}}],
                },
            ]
        }
        await g.async_pre_call_hook(UserAPIKeyAuth(), DualCache(), data, "acompletion")
        assert "AKIA" not in str(data) and "hunter2" not in str(data)

    @pytest.mark.asyncio
    async def test_key_opt_out(self):
        g = self._g()
        data = {"messages": [{"role": "user", "content": "AKIAIOSFODNN7EXAMPLE"}]}
        await g.async_pre_call_hook(UserAPIKeyAuth(metadata={"hide_secrets": False}), DualCache(), data, "acompletion")
        assert data["messages"][0]["content"] == "AKIAIOSFODNN7EXAMPLE"


# --------------------------------------------------------------------------- keyword / user blocklists
@pytest.mark.asyncio
async def test_banned_keywords(monkeypatch):
    from hangarllm.hangar.guardrails.banned_keywords import HangarBannedKeywords

    monkeypatch.setattr(hangarllm, "banned_keywords_list", ["hello"])
    hook = HangarBannedKeywords()
    with pytest.raises(HTTPException) as e:
        await hook.async_pre_call_hook(UserAPIKeyAuth(), DualCache(), {"messages": [{"role": "user", "content": "Hello world"}]}, "completion")
    assert e.value.status_code == 400
    await hook.async_pre_call_hook(UserAPIKeyAuth(), DualCache(), {"messages": [{"role": "user", "content": "hey"}]}, "completion")


@pytest.mark.asyncio
async def test_blocked_user_list(monkeypatch):
    from hangarllm.hangar.guardrails.blocked_user_list import HangarBlockedUserList

    monkeypatch.setattr(hangarllm, "blocked_user_list", ["bad-user"])
    hook = HangarBlockedUserList(prisma_client=None)
    with pytest.raises(HTTPException):
        await hook.async_pre_call_hook(UserAPIKeyAuth(), DualCache(), {"user": "bad-user"}, "completion")
    await hook.async_pre_call_hook(UserAPIKeyAuth(), DualCache(), {"user": "good-user"}, "completion")


@pytest.mark.asyncio
async def test_llm_guard_blocks_invalid_prompt():
    from hangarllm.hangar.guardrails.llm_guard import HangarLLMGuard

    hook = HangarLLMGuard(mock_testing=True, mock_redacted_text={"is_valid": False, "scanners": {"PromptInjection": 1.0}})
    with pytest.raises(HTTPException):
        await hook.async_moderation_hook({"messages": [{"role": "user", "content": "ignore all"}]}, UserAPIKeyAuth(), "completion")


def test_llama_guard_prompt_format(monkeypatch):
    from hangarllm.hangar.guardrails.llama_guard import HangarLlamaGuard

    monkeypatch.setattr(hangarllm, "llamaguard_model_name", "together_ai/meta-llama/Llama-Guard-3-8B")
    prompt = HangarLlamaGuard().build_prompt([{"role": "user", "content": "hi"}])
    assert "<BEGIN UNSAFE CONTENT CATEGORIES>" in prompt and "User: hi" in prompt


# --------------------------------------------------------------------------- route toggles
class TestRouteChecks:
    def test_admin_routes_disabled(self, monkeypatch):
        from hangarllm.hangar.proxy.route_checks import HangarRouteChecks

        monkeypatch.setenv("DISABLE_ADMIN_ENDPOINTS", "true")
        monkeypatch.delenv("DISABLE_LLM_API_ENDPOINTS", raising=False)
        with pytest.raises(HTTPException) as e:
            HangarRouteChecks.should_call_route("/key/generate")
        assert e.value.status_code == 403
        HangarRouteChecks.should_call_route("/chat/completions")

    def test_llm_routes_disabled_but_models_listed(self, monkeypatch):
        from hangarllm.hangar.proxy.route_checks import HangarRouteChecks

        monkeypatch.setenv("DISABLE_LLM_API_ENDPOINTS", "true")
        monkeypatch.delenv("DISABLE_ADMIN_ENDPOINTS", raising=False)
        with pytest.raises(HTTPException):
            HangarRouteChecks.should_call_route("/v1/chat/completions")
        HangarRouteChecks.should_call_route("/v1/models")
        HangarRouteChecks.should_call_route("/key/generate")


# --------------------------------------------------------------------------- custom auth modes
@pytest.mark.asyncio
@pytest.mark.parametrize("mode,raises,expected", [("on", True, None), ("auto", False, None), ("off", False, None)])
async def test_custom_auth_modes(monkeypatch, mode, raises, expected):
    from hangarllm.hangar.proxy import custom_auth, proxy_config

    monkeypatch.setattr(proxy_config, "custom_auth_settings", {"mode": mode})
    failing = AsyncMock(side_effect=ValueError("nope"))
    if raises:
        with pytest.raises(ValueError):
            await custom_auth.enterprise_custom_auth(MagicMock(), "k", failing)
    else:
        assert await custom_auth.enterprise_custom_auth(MagicMock(), "k", failing) is expected
    if mode == "off":
        failing.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_config_validates_mode():
    from hangarllm.hangar.proxy.proxy_config import HangarProxyConfig

    with pytest.raises(ValueError):
        await HangarProxyConfig().load_enterprise_config({"custom_auth_settings": {"mode": "maybe"}})


# --------------------------------------------------------------------------- key defaults
def test_team_org_and_key_defaults_inherited():
    from hangarllm.hangar.proxy.key_management import apply_enterprise_key_management_params
    from hangarllm.proxy._types import GenerateKeyRequest

    team = SimpleNamespace(organization_id="org-1", metadata={"key_defaults": {"max_budget": 5.0, "bogus": 1}})
    data = apply_enterprise_key_management_params(GenerateKeyRequest(team_id="t"), team)
    assert data.organization_id == "org-1" and data.max_budget == 5.0
    keep = apply_enterprise_key_management_params(GenerateKeyRequest(team_id="t", organization_id="mine", max_budget=1.0), team)
    assert keep.organization_id == "mine" and keep.max_budget == 1.0


# --------------------------------------------------------------------------- pagerduty
@pytest.mark.asyncio
async def test_pagerduty_alerts_at_threshold(monkeypatch):
    from hangarllm.hangar.callbacks.pagerduty import PAGERDUTY_EVENTS_URL, PagerDutyAlerting

    monkeypatch.setenv("PAGERDUTY_API_KEY", "rk")
    monkeypatch.setattr(hangarllm, "disable_aiohttp_transport", True)
    hangarllm.in_memory_llm_clients_cache.flush_cache()
    logger = PagerDutyAlerting(alerting_args={"failure_threshold": 2, "failure_threshold_window_seconds": 60})
    payload = {"error_information": {"error_class": "RateLimitError", "error_code": "429", "llm_provider": "openai"}, "metadata": {}}
    with respx.mock() as mock:
        route = mock.post(PAGERDUTY_EVENTS_URL).mock(return_value=httpx.Response(202))
        await logger.async_log_failure_event({"standard_logging_object": payload}, None, None, None)
        assert route.call_count == 0
        await logger.async_log_failure_event({"standard_logging_object": payload}, None, None, None)
        assert route.call_count == 1
        body = route.calls.last.request.content.decode()
        assert '"routing_key":"rk"' in body.replace(" ", "") and "RateLimitError" in body


def test_pagerduty_requires_routing_key(monkeypatch):
    from hangarllm.hangar.callbacks.pagerduty import PagerDutyAlerting

    monkeypatch.delenv("PAGERDUTY_API_KEY", raising=False)
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
    with pytest.raises(ValueError):
        PagerDutyAlerting()


# --------------------------------------------------------------------------- emails
class TestEmails:
    def test_templates_escape_and_brand(self):
        from hangarllm.hangar.emails import templates

        subject, html = templates.key_created_email(
            recipient="<script>x</script>", key="sk-123", max_budget=10, key_alias="a", base_url="http://gw", logo_url=None, support="ops@x.io"
        )
        assert "HangarLLM" in subject and "<script>" not in html and "#F5B301" in html and "sk-123" in html

    @pytest.mark.asyncio
    async def test_settings_default_without_db(self, monkeypatch):
        from hangarllm.hangar.emails import settings

        monkeypatch.setattr(settings, "_prisma_client", lambda: None)
        loaded = await settings.load_email_settings(use_cache=False)
        assert loaded["New User Invitation"] is True and loaded["Virtual Key Created"] is False

    @pytest.mark.asyncio
    async def test_key_created_email_respects_toggle_and_sends(self, monkeypatch):
        from hangarllm.hangar.emails import base_email
        from hangarllm.hangar.emails.types import EmailEvent, SendKeyCreatedEmailEvent
        from hangarllm.proxy._types import Hangarllm_EntityType

        logger = base_email.BaseEmailLogger()
        logger.send_email = AsyncMock()
        event = SendKeyCreatedEmailEvent(
            virtual_key="sk-abc", event="key_created", event_group=Hangarllm_EntityType.KEY, event_message="x",
            token="h", spend=0.0, max_budget=None, user_email="dev@corp.io",
        )
        monkeypatch.setattr(base_email, "is_email_event_enabled", AsyncMock(return_value=False))
        await logger.send_key_created_email(event)
        logger.send_email.assert_not_called()
        monkeypatch.setattr(base_email, "is_email_event_enabled", AsyncMock(side_effect=lambda e: e == EmailEvent.virtual_key_created))
        await logger.send_key_created_email(event)
        assert logger.send_email.await_args.kwargs["to_email"] == ["dev@corp.io"]

    @pytest.mark.asyncio
    async def test_budget_alert_deduplicated(self, monkeypatch):
        from hangarllm.hangar.emails import base_email
        from hangarllm.proxy._types import Hangarllm_EntityType
        from hangarllm.types.integrations.slack_alerting import CallInfo

        monkeypatch.setattr(base_email, "is_email_event_enabled", AsyncMock(return_value=True))
        logger = base_email.BaseEmailLogger()
        logger.send_email = AsyncMock()
        info = CallInfo(spend=9.0, max_budget=10.0, token="tok", user_email="a@b.io", event_group=Hangarllm_EntityType.KEY)
        await logger.budget_alerts(type="max_budget_alert", user_info=info)
        await logger.budget_alerts(type="max_budget_alert", user_info=info)
        assert logger.send_email.await_count == 1


# --------------------------------------------------------------------------- audit filters
def test_audit_where_builder():
    from hangarllm.hangar.proxy.audit_logs import build_audit_where

    where = build_audit_where(action="update", object_team_id="t1", search="key", start_date="2026-01-01")
    assert where["action"] == "update" and "gte" in where["updated_at"] and len(where["AND"]) == 2
    with pytest.raises(HTTPException):
        build_audit_where(end_date="yesterday")


# --------------------------------------------------------------------------- managed files
class TestManagedFiles:
    def _hook(self):
        from hangarllm.hangar.proxy.managed_files import HangarManagedFiles

        hook = HangarManagedFiles(internal_usage_cache=DualCache(), prisma_client=MagicMock())
        return hook

    def test_unified_ids_round_trip(self):
        from hangarllm.hangar.proxy.managed_files import decode_unified_id, make_unified_file_id
        from hangarllm.proxy.openai_files_endpoints.common_utils import (
            get_batch_id_from_unified_batch_id,
            get_model_id_from_unified_batch_id,
            get_models_from_unified_file_id,
        )

        fid = make_unified_file_id("application/jsonl", ["gpt-4o", "claude"])
        assert get_models_from_unified_file_id(decode_unified_id(fid)) == ["gpt-4o", "claude"]
        bid = self._hook().get_unified_batch_id(batch_id="batch_1", model_id="m-1")
        decoded = decode_unified_id(bid)
        assert get_model_id_from_unified_batch_id(decoded) == "m-1"
        assert get_batch_id_from_unified_batch_id(decoded) == "batch_1"
        assert decode_unified_id("file-abc") is None

    @pytest.mark.asyncio
    async def test_access_control(self):
        hook = self._hook()
        row = SimpleNamespace(created_by="alice", team_id="t1")
        hook._files = lambda: SimpleNamespace(find_first=AsyncMock(return_value=row))
        assert await hook.can_user_call_unified_file_id("x", UserAPIKeyAuth(user_id="alice")) is True
        assert await hook.can_user_call_unified_file_id("x", UserAPIKeyAuth(user_id="bob")) is False
        assert await hook.can_user_call_unified_file_id("x", UserAPIKeyAuth(user_id="bob", user_role=HangarllmUserRoles.PROXY_ADMIN)) is True
        assert await hook.can_user_call_unified_file_id("x", UserAPIKeyAuth(team_id="t1")) is True

    @pytest.mark.asyncio
    async def test_pre_call_maps_file_ids_and_routes_batches(self):
        from hangarllm.hangar.proxy.managed_files import make_unified_file_id
        from hangarllm.models.managed_files import HangarLLM_ManagedFileTable

        hook = self._hook()
        fid = make_unified_file_id("application/pdf", ["gpt-4o"])
        hook.can_user_call_unified_file_id = AsyncMock(return_value=True)
        hook.get_unified_file_id = AsyncMock(
            return_value=HangarLLM_ManagedFileTable(unified_file_id=fid, model_mappings={"dep-1": "file-xyz"}, flat_model_file_ids=["file-xyz"])
        )
        data = {"messages": [{"role": "user", "content": [{"type": "file", "file": {"file_id": fid}}]}]}
        out = await hook.async_pre_call_hook(UserAPIKeyAuth(user_id="u"), DualCache(), data, "acompletion")
        assert out["model_file_id_mapping"] == {fid: {"dep-1": "file-xyz"}}

        kwargs = {"input_file_id": fid, "model_info": {"id": "dep-1"}, "model_file_id_mapping": out["model_file_id_mapping"]}
        assert (await hook.async_pre_call_deployment_hook(kwargs, None))["input_file_id"] == "file-xyz"

        bid = hook.get_unified_batch_id(batch_id="batch_9", model_id="dep-1")
        hook.can_user_call_unified_object_id = AsyncMock(return_value=True)
        routed = await hook.async_pre_call_hook(UserAPIKeyAuth(user_id="u"), DualCache(), {"batch_id": bid}, "aretrieve_batch")
        assert routed["batch_id"] == "batch_9" and routed["model"] == "dep-1"

    @pytest.mark.asyncio
    async def test_foreign_file_rejected(self):
        from hangarllm.hangar.proxy.managed_files import make_unified_file_id

        hook = self._hook()
        hook.can_user_call_unified_file_id = AsyncMock(return_value=False)
        fid = make_unified_file_id("text/plain", ["m"])
        with pytest.raises(HTTPException) as e:
            await hook.async_pre_call_hook(UserAPIKeyAuth(user_id="u"), DualCache(), {"input_file_id": fid}, "acreate_batch")
        assert e.value.status_code == 403


# --------------------------------------------------------------------------- wiring
def test_core_wiring():
    from hangarllm.hangarllm_core_utils.custom_logger_registry import CustomLoggerRegistry
    from hangarllm.proxy.hooks import PROXY_HOOKS
    from hangarllm.proxy.utils import _get_email_logger_class

    assert {"managed_files", "managed_vector_stores"} <= set(PROXY_HOOKS)
    assert {"pagerduty", "smtp_email", "sendgrid_email", "resend_email", "generic_api"} <= set(
        CustomLoggerRegistry.CALLBACK_CLASS_STR_TO_CLASS_TYPE
    )
    assert _get_email_logger_class() is not None


def test_routes_mounted():
    from fastapi.testclient import TestClient

    import hangarllm.proxy.proxy_server as ps

    client = TestClient(ps.app)
    for path in ("/audit", "/email/event_settings", "/project/list"):
        assert client.get(path).status_code != 404, path
    assert ps.title == "HangarLLM API"
