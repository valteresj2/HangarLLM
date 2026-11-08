"""
Tests verifying that default_api_key_tpm_limit and default_api_key_rpm_limit set in
hangarllm_params are returned by the /model/info endpoint.
"""

import json
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from hangarllm.proxy.proxy_server import _get_proxy_model_info
from hangarllm.types.router import Deployment, HangarLLM_Params, ModelInfo
from tests.unit.proxy.router_entry_point_stubs import route_entry_points_to_stubs


def _make_deployment(
    model_name: str,
    default_tpm: Optional[int] = None,
    default_rpm: Optional[int] = None,
) -> Deployment:
    params: dict = {"model": f"openai/{model_name}"}
    if default_tpm is not None:
        params["default_api_key_tpm_limit"] = default_tpm
    if default_rpm is not None:
        params["default_api_key_rpm_limit"] = default_rpm
    return Deployment(
        model_name=model_name,
        hangarllm_params=HangarLLM_Params(**params),
        model_info=ModelInfo(),
    )


class TestModelInfoDefaultLimitsInResponse:
    """
    Verify _get_proxy_model_info (the helper used by the /model/info endpoint) returns
    default_api_key_tpm_limit and default_api_key_rpm_limit from hangarllm_params.
    """

    def test_default_tpm_and_rpm_present_in_model_info_response(self):
        """Both defaults should appear in the hangarllm_params section of the response."""
        deployment = _make_deployment("model1", default_tpm=100, default_rpm=200)
        model_dict = deployment.model_dump(exclude_none=True)

        result = _get_proxy_model_info(model=model_dict)

        hangarllm_params = result["hangarllm_params"]
        assert hangarllm_params.get("default_api_key_tpm_limit") == 100
        assert hangarllm_params.get("default_api_key_rpm_limit") == 200

    def test_default_tpm_only_present_when_only_tpm_configured(self):
        """Only the configured default appears; the other stays absent."""
        deployment = _make_deployment("model1", default_tpm=500)
        model_dict = deployment.model_dump(exclude_none=True)

        result = _get_proxy_model_info(model=model_dict)

        hangarllm_params = result["hangarllm_params"]
        assert hangarllm_params.get("default_api_key_tpm_limit") == 500
        assert "default_api_key_rpm_limit" not in hangarllm_params

    def test_default_rpm_only_present_when_only_rpm_configured(self):
        """Only the configured default appears; the other stays absent."""
        deployment = _make_deployment("model1", default_rpm=300)
        model_dict = deployment.model_dump(exclude_none=True)

        result = _get_proxy_model_info(model=model_dict)

        hangarllm_params = result["hangarllm_params"]
        assert hangarllm_params.get("default_api_key_rpm_limit") == 300
        assert "default_api_key_tpm_limit" not in hangarllm_params

    def test_defaults_absent_when_not_configured(self):
        """Neither field appears when not set on the deployment."""
        deployment = _make_deployment("model1")
        model_dict = deployment.model_dump(exclude_none=True)

        result = _get_proxy_model_info(model=model_dict)

        hangarllm_params = result["hangarllm_params"]
        assert "default_api_key_tpm_limit" not in hangarllm_params
        assert "default_api_key_rpm_limit" not in hangarllm_params

    def test_defaults_not_masked_or_stripped_by_sensitive_data_filter(self):
        """
        default_api_key_tpm_limit / default_api_key_rpm_limit must not be
        treated as sensitive and must survive remove_sensitive_info_from_deployment.
        They contain "key" which normally triggers masking; the call site explicitly
        excludes these two fields via excluded_keys rather than widening the global
        non_sensitive_overrides.
        """
        deployment = _make_deployment("model1", default_tpm=100, default_rpm=200)
        model_dict = deployment.model_dump(exclude_none=True)

        result = _get_proxy_model_info(model=model_dict)

        # Values should be unchanged integers, not masked strings
        assert result["hangarllm_params"]["default_api_key_tpm_limit"] == 100
        assert result["hangarllm_params"]["default_api_key_rpm_limit"] == 200


class TestModelInfoEndpointWithRouter:
    """
    Integration-style tests simulating the /model/info endpoint reading from the router.
    """

    @pytest.mark.asyncio
    async def test_model_info_endpoint_returns_defaults_for_specific_model_id(self):
        """
        When hangarllm_model_id is provided, the endpoint should return the deployment's
        default limits in hangarllm_params.
        """
        from hangarllm.proxy.proxy_server import model_info_v1
        from hangarllm.proxy._types import UserAPIKeyAuth

        deployment = _make_deployment("model1", default_tpm=100, default_rpm=200)

        mock_router = route_entry_points_to_stubs(MagicMock())
        mock_router.get_deployment.return_value = deployment

        user_api_key_dict = UserAPIKeyAuth(api_key="sk-test")

        with (
            patch("hangarllm.proxy.proxy_server.llm_router", mock_router),
            patch("hangarllm.proxy.proxy_server.llm_model_list", []),
            patch("hangarllm.proxy.proxy_server.user_model", None),
        ):
            response = await model_info_v1(
                user_api_key_dict=user_api_key_dict,
                hangarllm_model_id="some-model-id",
            )

        data = json.loads(response.body)["data"]
        assert len(data) == 1
        hangarllm_params = data[0]["hangarllm_params"]
        assert hangarllm_params.get("default_api_key_tpm_limit") == 100
        assert hangarllm_params.get("default_api_key_rpm_limit") == 200

    @pytest.mark.asyncio
    async def test_model_info_endpoint_returns_defaults_in_full_model_list(self):
        """
        Without hangarllm_model_id, the endpoint iterates all models. Each deployment's
        default limits should appear in its hangarllm_params entry.
        """
        from hangarllm.proxy.proxy_server import model_info_v1
        from hangarllm.proxy._types import UserAPIKeyAuth

        deployment = _make_deployment("model1", default_tpm=100, default_rpm=200)
        deployment_dict = deployment.model_dump(exclude_none=True)

        mock_router = route_entry_points_to_stubs(MagicMock())
        mock_router.model_list = [deployment_dict]
        mock_router.get_model_names.return_value = ["model1"]
        mock_router.get_model_access_groups.return_value = {}

        user_api_key_dict = UserAPIKeyAuth(api_key="sk-test")

        with (
            patch("hangarllm.proxy.proxy_server.llm_router", mock_router),
            patch("hangarllm.proxy.proxy_server.llm_model_list", [deployment_dict]),
            patch("hangarllm.proxy.proxy_server.user_model", None),
            patch("hangarllm.proxy.proxy_server.prisma_client", None),
            patch("hangarllm.proxy.proxy_server.get_key_models", return_value=["model1"]),
            patch(
                "hangarllm.proxy.proxy_server.get_team_models", return_value=["model1"]
            ),
            patch(
                "hangarllm.proxy.proxy_server.get_complete_model_list",
                return_value=["model1"],
            ),
        ):
            response = await model_info_v1(
                user_api_key_dict=user_api_key_dict,
                hangarllm_model_id=None,
            )

        data = json.loads(response.body)["data"]
        assert len(data) >= 1
        hangarllm_params = data[0]["hangarllm_params"]
        assert hangarllm_params.get("default_api_key_tpm_limit") == 100
        assert hangarllm_params.get("default_api_key_rpm_limit") == 200
