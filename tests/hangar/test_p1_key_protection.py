import asyncio
import base64
import hashlib
import hmac
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi import HTTPException

import hangarllm
from hangarllm.hangar.guardrails.secret_detection import SecretScanner, default_secret_guardrail
from hangarllm.hangar.proxy.envelope import (
    EnvelopeError,
    VaultTransit,
    kms_client,
    unwrap_salt_key_from_kms,
)
from hangarllm.hangar.proxy.key_format import generate_virtual_key, has_valid_checksum
from hangarllm.hangar.proxy import key_policy as key_policy_module
from hangarllm.hangar.proxy.key_network import InvalidAllowedIps, allowed_networks, enforce_key_allowed_ips
from hangarllm.hangar.proxy.key_policy import (
    PRODUCTION,
    KeyPolicy,
    enforce_key_policy,
    enforce_key_update_policy,
    key_policy_from,
    key_policy_violations,
    validate_project_environment,
)
from hangarllm.hangar.proxy.leak_report import valid_signature
from hangarllm.proxy.common_utils.encrypt_decrypt_utils import (
    V2_GCM_PREFIX,
    decrypt_value_helper,
    encrypt_value,
    encrypt_value_helper,
)


def _key_request(**overrides):
    values = {
        "duration": "30d",
        "max_budget": 10.0,
        "budget_id": None,
        "models": ["gpt"],
        "key_type": "llm_api",
        "key_alias": "svc",
        "auto_rotate": None,
        "rotation_interval": None,
        "metadata": None,
    }
    return SimpleNamespace(**{**values, **overrides})


class TestKeyFormat:
    def test_generated_keys_are_prefixed_unique_and_valid(self):
        keys = {generate_virtual_key() for _ in range(200)}
        assert len(keys) == 200
        assert all(key.startswith("hgr_") and len(key) == 42 and has_valid_checksum(key) for key in keys)

    def test_a_single_changed_character_fails_the_checksum(self):
        key = generate_virtual_key()
        replacement = "A" if key[10] != "A" else "B"
        assert not has_valid_checksum(key[:10] + replacement + key[11:])

    @pytest.mark.parametrize("candidate", ["sk-abcdefghijklmnopqrstuv", "hgr_short", "hgr_" + "!" * 38, ""])
    def test_other_shapes_are_rejected(self, candidate):
        assert not has_valid_checksum(candidate)

    def test_gitleaks_rule_matches_generated_keys(self):
        config = (Path(__file__).resolve().parents[2] / ".gitleaks.toml").read_text()
        pattern = re.search(r"regex = '''(.+?)'''", config).group(1)
        assert re.search(pattern, f"token = {generate_virtual_key()}")

    def test_secret_scanner_and_log_redaction_catch_the_new_format(self):
        key = generate_virtual_key()
        assert [name for name, _, _ in SecretScanner().find(f"use {key} please")] == ["hangar_virtual_key"]
        from hangarllm.hangarllm_core_utils.secret_redaction import redact_string

        assert key not in redact_string(f"authenticating with {key}")


class TestKeyPolicy:
    def test_a_complete_request_passes(self):
        assert key_policy_violations(_key_request(), None, KeyPolicy()) == ()

    @pytest.mark.parametrize(
        ("overrides", "fragment"),
        [
            ({"duration": None}, "duration is required"),
            ({"duration": "365d"}, "longer than 90d"),
            ({"max_budget": None}, "max_budget"),
            ({"models": []}, "models is required"),
        ],
    )
    def test_each_gap_is_reported(self, overrides, fragment):
        (problem,) = key_policy_violations(_key_request(**overrides), None, KeyPolicy())
        assert fragment in problem

    def test_a_team_budget_or_budget_id_satisfies_the_budget_rule(self):
        no_budget = _key_request(max_budget=None)
        assert key_policy_violations(no_budget, SimpleNamespace(max_budget=5.0), KeyPolicy()) == ()
        assert key_policy_violations(_key_request(max_budget=None, budget_id="b1"), None, KeyPolicy()) == ()

    def test_management_keys_do_not_need_models(self):
        assert key_policy_violations(_key_request(models=[], key_type="management"), None, KeyPolicy()) == ()

    def test_settings_tune_or_disable_the_policy(self):
        relaxed = key_policy_from({"key_policy": {"require_budget": False, "max_duration": None}}, environ={})
        assert key_policy_violations(_key_request(max_budget=None, duration="999d"), None, relaxed) == ()
        off = key_policy_from({}, environ={"HANGARLLM_DISABLE_KEY_POLICY": "true"})
        assert key_policy_violations(_key_request(duration=None, models=[]), None, off) == ()

    def test_a_violation_is_a_client_error(self, monkeypatch):
        monkeypatch.delenv("HANGARLLM_DISABLE_KEY_POLICY", raising=False)
        with pytest.raises(HTTPException) as caught:
            enforce_key_policy(_key_request(duration=None), None, {})
        assert caught.value.status_code == 400 and "duration" in str(caught.value.detail)

    def test_rotation_turns_on_only_when_the_new_key_can_be_delivered(self, monkeypatch):
        monkeypatch.delenv("HANGARLLM_DISABLE_KEY_POLICY", raising=False)
        monkeypatch.setattr(hangarllm, "_key_management_settings", SimpleNamespace(store_virtual_keys=False))
        no_delivery = _key_request()
        enforce_key_policy(no_delivery, None, {})
        assert no_delivery.auto_rotate is None

        monkeypatch.setattr(hangarllm, "_key_management_settings", SimpleNamespace(store_virtual_keys=True))
        delivered = _key_request()
        enforce_key_policy(delivered, None, {})
        assert delivered.auto_rotate is True and delivered.rotation_interval == "30d"

        opted_out = _key_request(auto_rotate=False)
        enforce_key_policy(opted_out, None, {})
        assert opted_out.auto_rotate is False


class TestLeakReportSignature:
    def test_only_the_exact_hmac_is_accepted(self):
        body = b'[{"token": "x"}]'
        good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        assert valid_signature("secret", body, good)
        assert not valid_signature("other", body, good)
        assert not valid_signature("secret", body + b" ", good)
        assert not valid_signature("secret", body, None)


class TestEncryptionDefaults:
    @pytest.fixture(autouse=True)
    def _salt(self, monkeypatch):
        monkeypatch.setenv("HANGARLLM_SALT_KEY", "unit-test-salt")
        monkeypatch.setattr("hangarllm.proxy.proxy_server.general_settings", {})

    def test_new_values_use_aes_gcm_by_default(self):
        sealed = encrypt_value_helper("provider-key")
        assert sealed.startswith(V2_GCM_PREFIX)
        assert decrypt_value_helper(sealed, key="k") == "provider-key"

    def test_values_written_with_the_legacy_cipher_still_decrypt(self):
        legacy = base64.urlsafe_b64encode(encrypt_value("provider-key", "unit-test-salt")).decode()
        assert decrypt_value_helper(legacy, key="k") == "provider-key"

    def test_operators_can_keep_the_legacy_cipher(self, monkeypatch):
        monkeypatch.setattr(
            "hangarllm.proxy.proxy_server.general_settings", {"encryption_algorithm": "xsalsa20-poly1305"}
        )
        assert not encrypt_value_helper("provider-key").startswith(V2_GCM_PREFIX)


class _FakeKms:
    def wrap(self, plaintext):
        return base64.b64encode(plaintext[::-1]).decode()

    def unwrap(self, wrapped):
        return base64.b64decode(wrapped)[::-1]


class TestEnvelope:
    WRAPPED = _FakeKms().wrap(b"the-salt")

    def test_wrapped_salt_is_opened_by_the_kms(self):
        env = {"HANGARLLM_SALT_KEY_WRAPPED": self.WRAPPED}
        assert unwrap_salt_key_from_kms(env, lambda _: _FakeKms()) == "the-salt"

    def test_no_envelope_means_nothing_to_do(self):
        assert unwrap_salt_key_from_kms({}, lambda _: _FakeKms()) is None

    def test_plain_and_wrapped_salt_together_are_refused(self):
        env = {"HANGARLLM_SALT_KEY_WRAPPED": self.WRAPPED, "HANGARLLM_SALT_KEY": "plain"}
        with pytest.raises(EnvelopeError, match="not both"):
            unwrap_salt_key_from_kms(env, lambda _: _FakeKms())

    def test_kms_failure_stops_startup_without_leaking_details(self):
        def failing(_):
            raise RuntimeError("secret-detail-from-sdk")

        with pytest.raises(EnvelopeError) as caught:
            unwrap_salt_key_from_kms({"HANGARLLM_SALT_KEY_WRAPPED": self.WRAPPED}, failing)
        assert "secret-detail-from-sdk" not in str(caught.value)

    @pytest.mark.parametrize(
        "env",
        [
            {"HANGARLLM_KMS_PROVIDER": "vault"},
            {"HANGARLLM_KMS_PROVIDER": "nope", "HANGARLLM_KMS_KEY_ID": "k"},
            {"HANGARLLM_KMS_PROVIDER": "vault", "HANGARLLM_KMS_KEY_ID": "k"},
        ],
    )
    def test_incomplete_settings_are_explained(self, env):
        with pytest.raises(EnvelopeError):
            kms_client(env)

    @respx.mock
    def test_vault_transit_round_trip(self):
        encrypted = respx.post("https://vault.test/v1/transit/encrypt/salt").mock(
            return_value=httpx.Response(200, json={"data": {"ciphertext": "vault:v1:abc"}})
        )
        respx.post("https://vault.test/v1/transit/decrypt/salt").mock(
            return_value=httpx.Response(200, json={"data": {"plaintext": base64.b64encode(b"the-salt").decode()}})
        )
        vault = VaultTransit("salt", "https://vault.test", "tok")
        assert vault.wrap(b"the-salt") == "vault:v1:abc"
        assert vault.unwrap("vault:v1:abc") == b"the-salt"
        assert encrypted.calls[0].request.headers["x-vault-token"] == "tok"


class TestDefaultSecretGuardrail:
    def test_provider_keys_are_masked_before_the_provider_sees_them(self):
        guardrail = default_secret_guardrail()
        request = {"messages": [{"role": "user", "content": "my key is AKIAIOSFODNN7EXAMPLE ok"}]}
        assert guardrail.redact_request(request)
        assert "AKIAIOSFODNN7EXAMPLE" not in request["messages"][0]["content"]

    def test_generic_looking_assignments_are_left_alone(self):
        guardrail = default_secret_guardrail()
        text = 'password = "hunter2hunter2" and qpdf --password=mypassword'
        request = {"messages": [{"role": "user", "content": text}]}
        guardrail.redact_request(request)
        assert request["messages"][0]["content"] == text


_IPS = {"allowed_ips": ["203.0.113.0/24"]}


class TestProductionKeys:
    def test_a_restricted_key_may_skip_the_expiry(self):
        request = _key_request(duration=None, metadata=_IPS)
        assert key_policy_violations(request, None, KeyPolicy(), PRODUCTION) == ()

    def test_a_rotating_key_may_skip_the_expiry_only_when_rotation_can_deliver(self):
        request = _key_request(duration=None, auto_rotate=True, rotation_interval="30d")
        assert key_policy_violations(request, None, KeyPolicy(), PRODUCTION, rotation_can_deliver=True) == ()
        assert key_policy_violations(request, None, KeyPolicy(), PRODUCTION, rotation_can_deliver=False)

    def test_an_unprotected_key_with_no_expiry_is_refused(self):
        (problem,) = key_policy_violations(_key_request(duration=None), None, KeyPolicy(), PRODUCTION)
        assert "allowed_ips" in problem

    def test_a_long_expiry_also_needs_protection_but_a_short_one_does_not(self):
        assert key_policy_violations(_key_request(duration="365d"), None, KeyPolicy(), PRODUCTION)
        assert key_policy_violations(_key_request(duration="30d"), None, KeyPolicy(), PRODUCTION) == ()

    @pytest.mark.parametrize(
        ("overrides", "fragment"),
        [({"max_budget": None}, "max_budget"), ({"models": []}, "models"), ({"key_alias": None}, "key_alias")],
    )
    def test_budget_models_and_owner_stay_mandatory(self, overrides, fragment):
        (problem,) = key_policy_violations(_key_request(metadata=_IPS, **overrides), None, KeyPolicy(), PRODUCTION)
        assert fragment in problem

    @pytest.mark.parametrize("never", [None, "", "-1"])
    def test_experiment_keys_cannot_ask_to_never_expire(self, never):
        assert key_policy_violations(_key_request(duration=never), None, KeyPolicy())

    def test_an_unreadable_duration_is_reported_not_raised(self):
        assert "not valid" in key_policy_violations(_key_request(duration="soon"), None, KeyPolicy())[0]

    def test_project_environment_values_are_checked(self):
        validate_project_environment({"environment": "production"})
        validate_project_environment(None)
        with pytest.raises(HTTPException):
            validate_project_environment({"environment": "prod"})


class TestAllowedIps:
    def test_ips_and_networks_are_parsed(self):
        assert len(allowed_networks({"allowed_ips": ["203.0.113.4", "10.0.0.0/16", "2001:db8::/48"]})) == 3

    @pytest.mark.parametrize("metadata", [None, {}, {"allowed_ips": []}, {"allowed_ips": None}])
    def test_no_restriction(self, metadata):
        assert allowed_networks(metadata) == ()

    @pytest.mark.parametrize("entries", ["10.0.0.1", ["not-an-ip"], [1], ["0.0.0.0/0"], ["1.0.0.0/1"], ["::/0"]])
    def test_unusable_or_too_wide_entries_are_refused(self, entries):
        with pytest.raises(InvalidAllowedIps):
            allowed_networks({"allowed_ips": entries})

    def test_a_too_wide_network_fails_the_policy_even_as_protection(self):
        request = _key_request(duration=None, metadata={"allowed_ips": ["0.0.0.0/0"]})
        assert len(key_policy_violations(request, None, KeyPolicy(), PRODUCTION)) == 2

    @staticmethod
    def _request(ip):
        return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})

    def test_requests_are_matched_against_the_networks(self):
        enforce_key_allowed_ips(_IPS, self._request("203.0.113.9"), {})
        with pytest.raises(HTTPException) as caught:
            enforce_key_allowed_ips(_IPS, self._request("198.51.100.1"), {})
        assert caught.value.status_code == 403

    def test_a_corrupt_restriction_blocks_instead_of_opening_the_key(self):
        with pytest.raises(HTTPException):
            enforce_key_allowed_ips({"allowed_ips": ["nope"]}, self._request("203.0.113.9"), {})

    def test_an_unrestricted_key_does_not_read_the_request(self):
        enforce_key_allowed_ips({}, None, {})


def _stored_key(**overrides):
    values = {
        "expires": None,
        "max_budget": 5.0,
        "budget_id": None,
        "models": ["gpt"],
        "key_alias": "svc",
        "auto_rotate": False,
        "rotation_interval": None,
        "metadata": {},
        "project_id": None,
    }
    return SimpleNamespace(**{**values, **overrides})


def _update(**fields):
    return SimpleNamespace(model_fields_set=set(fields), **fields)


class TestKeyUpdates:
    @pytest.fixture(autouse=True)
    def _projects(self, monkeypatch):
        monkeypatch.delenv("HANGARLLM_DISABLE_KEY_POLICY", raising=False)
        self.managed = []

        async def project(project_id):
            environment = {"prod": "production", "lab": "experiment"}.get(project_id)
            return SimpleNamespace(metadata={"environment": environment}, team_id="t") if environment else None

        async def manager(user, found):
            self.managed.append(found)

        monkeypatch.setattr(key_policy_module, "_project_row", project)
        monkeypatch.setattr(key_policy_module, "_require_production_key_manager", manager)

    def _run(self, data, key):
        asyncio.run(enforce_key_update_policy(data, key, None, {}, "user"))

    @staticmethod
    def _soon():
        from datetime import datetime, timedelta, timezone

        return datetime.now(timezone.utc) + timedelta(days=20)

    @pytest.mark.parametrize("data", [{"duration": "-1"}, {"duration": None}, {"duration": "365d"}])
    def test_an_experiment_key_cannot_lose_its_expiry(self, data):
        with pytest.raises(HTTPException):
            self._run(_update(**data), _stored_key(expires=self._soon()))

    @pytest.mark.parametrize("data", [{"max_budget": None}, {"models": []}])
    def test_budget_and_models_cannot_be_removed(self, data):
        with pytest.raises(HTTPException):
            self._run(_update(**data), _stored_key(expires=self._soon()))

    def test_an_empty_duration_leaves_the_expiry_alone(self):
        self._run(_update(duration="", key_alias="renamed"), _stored_key(expires=self._soon()))

    def test_gaps_from_before_the_policy_do_not_block_other_edits(self):
        self._run(_update(key_alias="renamed", metadata={"a": 1}), _stored_key(expires=None, max_budget=None, models=[]))

    def test_unrelated_edits_are_not_examined(self):
        self._run(_update(tags=["a"]), _stored_key(expires=None, max_budget=None))

    def test_a_production_key_cannot_drop_its_only_protection(self):
        key = _stored_key(project_id="prod", metadata=_IPS)
        with pytest.raises(HTTPException):
            self._run(_update(metadata={}), key)

    def test_a_non_expiring_key_cannot_move_out_of_production(self):
        with pytest.raises(HTTPException):
            self._run(_update(project_id="lab"), _stored_key(project_id="prod", metadata=_IPS))
        with pytest.raises(HTTPException):
            self._run(_update(project_id=None), _stored_key(project_id="prod", metadata=_IPS))

    def test_moving_into_production_needs_protection_and_a_manager(self):
        with pytest.raises(HTTPException):
            self._run(_update(project_id="prod"), _stored_key(project_id="lab", expires=None))
        self._run(_update(project_id="prod", metadata=_IPS), _stored_key(project_id="lab", expires=self._soon()))
        assert len(self.managed) == 1

    def test_editing_a_production_key_needs_a_manager(self):
        self._run(_update(max_budget=9.0), _stored_key(project_id="prod", metadata=_IPS))
        assert len(self.managed) == 1

    def test_editing_an_experiment_key_does_not(self):
        self._run(_update(max_budget=9.0), _stored_key(project_id="lab", expires=self._soon()))
        assert self.managed == []


class TestProductionKeyManager:
    PROJECT = SimpleNamespace(team_id="t")

    @pytest.fixture(autouse=True)
    def _team(self, monkeypatch):
        from hangarllm.hangar.proxy import projects

        async def team(team_id):
            return SimpleNamespace(team_id=team_id)

        monkeypatch.setattr(projects, "_team", team)

    def _check(self, role, project=PROJECT):
        return asyncio.run(key_policy_module._require_production_key_manager(SimpleNamespace(user_role=role), project))

    def test_proxy_admins_are_allowed_without_a_team_lookup(self):
        self._check("proxy_admin", SimpleNamespace(team_id=None))

    def test_team_admins_are_allowed_and_members_are_not(self, monkeypatch):
        import hangarllm.proxy.management.teams.authz as authz

        monkeypatch.setattr(authz, "is_team_admin", lambda user, team: True)
        self._check("internal_user")
        monkeypatch.setattr(authz, "is_team_admin", lambda user, team: False)
        with pytest.raises(HTTPException) as caught:
            self._check("internal_user")
        assert caught.value.status_code == 403

    def test_a_project_without_a_team_is_for_proxy_admins_only(self):
        with pytest.raises(HTTPException):
            self._check("internal_user", SimpleNamespace(team_id=None))


class TestNewFormatIsAcceptedEverywhere:
    def test_block_and_unblock_validation_accepts_generated_keys(self):
        from hangarllm.proxy.utils import is_valid_api_key

        assert is_valid_api_key(generate_virtual_key())

    def test_no_code_guesses_a_key_from_a_substring(self):
        root = Path(__file__).resolve().parents[2] / "hangarllm" / "proxy"
        guesses = [
            path.name
            for path in root.rglob("*.py")
            if "_experimental" not in path.parts and re.search(r"""["']sk-?["'] not in""", path.read_text("utf-8"))
        ]
        assert guesses == []
