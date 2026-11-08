from collections.abc import Mapping

import pytest
from fastapi import HTTPException

import litellm
from litellm.decisions.call import _decisions_config
from litellm.hangar.decisions.formats import (
    OpenAIShapedDecisionsFormat,
    available_decisions_formats,
    register_decisions_format,
    reset_decisions_formats,
    resolve_decisions_format,
)
from litellm.llms.openai.decisions.transformation import OpenAIDecisionsConfig
from litellm.llms.openrouter.decisions.transformation import OpenRouterDecisionsConfig
from litellm.proxy.auth.auth_utils import is_request_body_safe
from litellm.types.decisions import DecisionsIRRequest, OpenAIDecisionRequestBody


class AcmeFormat(OpenAIShapedDecisionsFormat):
    path = "/acme/judge"
    description = "Acme judge"

    def to_wire(self, body: Mapping[str, object]) -> Mapping[str, object]:
        return {"acme_questions": body["questions"], "acme_model": body["model"]}

    def from_wire(self, payload: object) -> object:
        assert isinstance(payload, dict)
        return {"model": payload["model"], "answers": payload["results"], "usage": payload["usage"]}


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch):
    reset_decisions_formats()
    monkeypatch.setattr(litellm, "decisions_formats", None, raising=False)
    yield
    reset_decisions_formats()


def _request() -> DecisionsIRRequest:
    from litellm.llms.openai.decisions.transformation import openai_request_to_ir

    return openai_request_to_ir(
        OpenAIDecisionRequestBody.model_validate(
            {
                "model": "acme-1",
                "input": "I was charged twice",
                "questions": [{"type": "predicate", "name": "refund", "instructions": "Refund needed?"}],
            }
        )
    )


class TestResolution:
    def test_builtin_formats_resolve_to_their_configs(self):
        assert type(resolve_decisions_format("openai")) is OpenAIDecisionsConfig
        assert type(resolve_decisions_format("openrouter")) is OpenRouterDecisionsConfig

    def test_unknown_names_and_import_paths_do_not_resolve(self):
        assert resolve_decisions_format("nope") is None
        assert resolve_decisions_format("os.system") is None

    def test_registered_format_overrides_nothing_else(self):
        register_decisions_format("acme", AcmeFormat)
        assert isinstance(resolve_decisions_format("acme"), AcmeFormat)
        assert type(resolve_decisions_format("openai")) is OpenAIDecisionsConfig

    @pytest.mark.parametrize("name", ["Bad Name", "auto", "", "../x"])
    def test_invalid_names_are_rejected(self, name):
        with pytest.raises(ValueError):
            register_decisions_format(name, AcmeFormat)

    def test_only_decisions_configs_can_be_registered(self):
        with pytest.raises(TypeError):
            register_decisions_format("broken", object)

    def test_config_declared_format_loads_once_and_is_listed(self, monkeypatch):
        calls = []

        def fake_get_instance(path, config_file_path=None):
            calls.append(path)
            return AcmeFormat

        monkeypatch.setattr("litellm.proxy.types_utils.utils.get_instance_fn", fake_get_instance)
        monkeypatch.setattr(litellm, "decisions_formats", {"acme": "acme_decisions.AcmeFormat"}, raising=False)
        assert isinstance(resolve_decisions_format("acme"), AcmeFormat)
        assert isinstance(resolve_decisions_format("acme"), AcmeFormat)
        assert calls == ["acme_decisions.AcmeFormat"]
        listed = {item.name: item for item in available_decisions_formats()}
        assert listed["acme"].source == "custom" and listed["acme"].description == "Acme judge"
        assert listed["openai"].source == "builtin"

    def test_broken_plugin_is_unavailable_instead_of_crashing(self, monkeypatch):
        def failing(path, config_file_path=None):
            raise ImportError("missing module")

        monkeypatch.setattr("litellm.proxy.types_utils.utils.get_instance_fn", failing)
        monkeypatch.setattr(litellm, "decisions_formats", {"acme": "missing.Format"}, raising=False)
        assert resolve_decisions_format("acme") is None
        assert "acme" not in {item.name for item in available_decisions_formats()}


class TestCustomFormatRoundTrip:
    def test_request_goes_out_in_the_custom_shape(self):
        body = AcmeFormat().transform_decisions_request("acme-1", _request(), "openai")
        assert set(body) == {"acme_questions", "acme_model"}
        assert body["acme_model"] == "acme-1"
        assert body["acme_questions"][0]["name"] == "refund"

    def test_response_comes_back_as_openai_answers(self):
        answers = [{"type": "predicate", "name": "refund", "probability": 0.9}]
        usage = {"input_tokens": 5, "output_tokens": 0, "total_tokens": 5}
        parsed = AcmeFormat().parse_response({"model": "acme-1", "results": answers, "usage": usage}, _request())
        (answer,) = parsed.answers
        assert answer.probability == 0.9


class TestDeploymentSelection:
    def test_deployment_format_replaces_the_provider_default(self):
        config = _decisions_config("gpt-6-luna", "openai", "openrouter")
        assert type(config) is OpenRouterDecisionsConfig

    @pytest.mark.parametrize("unset", [None, "", "auto"])
    def test_unset_format_keeps_the_provider_default(self, unset):
        assert type(_decisions_config("x", "openrouter", unset)) is OpenRouterDecisionsConfig

    def test_unknown_format_is_a_clear_client_error(self):
        with pytest.raises(litellm.BadRequestError, match="openrouter"):
            _decisions_config("x", "openai", "nope")


def test_callers_cannot_pick_the_format_from_the_request_body():
    with pytest.raises((ValueError, HTTPException), match="decisions_format"):
        is_request_body_safe({"model": "m", "decisions_format": "acme"}, {}, None, "m", route="/v1/decisions")
