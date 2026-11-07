"""HangarLLM entitlement: every feature is on, nothing phones home, operators can opt features out."""

import pytest

from litellm.proxy.auth.litellm_license import (
    AUTO_ROUTER_LICENSE_FEATURE,
    LicenseCheck,
)


def test_every_deployment_is_entitled() -> None:
    check = LicenseCheck()
    assert check.is_premium() is True
    assert check.verify_license_without_api_request(public_key=None, license_key="anything") is True


def test_no_seat_or_team_limits() -> None:
    check = LicenseCheck()
    assert check.user_seat_limit() is None
    assert check.is_over_limit(10**9) is False
    assert check.is_team_count_over_limit(10**9) is False


def test_never_contacts_a_license_server() -> None:
    check = LicenseCheck()
    assert check.base_url == ""
    assert not hasattr(check, "http_handler")


def test_all_features_granted_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HANGARLLM_DISABLED_FEATURES", raising=False)
    check = LicenseCheck()
    assert check.grants_feature(AUTO_ROUTER_LICENSE_FEATURE) is True
    assert check.grants_feature("sso") is True
    assert check.auto_router_capability_limit() is None


def test_operator_can_disable_features(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HANGARLLM_DISABLED_FEATURES", " auto_router , sso ")
    check = LicenseCheck()
    assert check.grants_feature("auto_router") is False
    assert check.grants_feature("sso") is False
    assert check.grants_feature("audit_logs") is True
    assert check.auto_router_capability_limit() == 1
