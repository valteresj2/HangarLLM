"""
Test that HangarLLM_Params and GenericHangarLLMParams handle reserved keys gracefully.

This test verifies the fix for the bug where passing a dict containing 'self',
'params', or '__class__' keys to HangarLLM_Params() would cause:
    TypeError: HangarLLM_Params.__init__() got multiple values for argument 'self'
"""

import pytest

from hangarllm.types.router import GenericHangarLLMParams, HangarLLM_Params


class TestHangarLLMParamsReservedKeys:
    """Test that reserved keys in input data are filtered out gracefully."""

    def test_hangarllm_params_with_self_key(self):
        """Test HangarLLM_Params handles 'self' key in input dict."""
        params_dict = {"model": "gpt-4", "self": "some_value", "api_key": "test-key"}
        params = HangarLLM_Params(**params_dict)
        assert params.model == "gpt-4"
        assert params.api_key == "test-key"
        assert not hasattr(params, "self") or params.get("self") is None

    def test_hangarllm_params_with_params_key(self):
        """Test HangarLLM_Params handles 'params' key in input dict."""
        params_dict = {"model": "gpt-4", "params": "bad_value"}
        params = HangarLLM_Params(**params_dict)
        assert params.model == "gpt-4"

    def test_hangarllm_params_with_class_key(self):
        """Test HangarLLM_Params handles '__class__' key in input dict."""
        params_dict = {"model": "gpt-4", "__class__": "bad_value"}
        params = HangarLLM_Params(**params_dict)
        assert params.model == "gpt-4"

    def test_generic_hangarllm_params_with_self_key(self):
        """Test GenericHangarLLMParams handles 'self' key in input dict."""
        params_dict = {"self": "some_value", "api_key": "test-key"}
        params = GenericHangarLLMParams(**params_dict)
        assert params.api_key == "test-key"

    def test_generic_hangarllm_params_with_params_key(self):
        """Test GenericHangarLLMParams handles 'params' key in input dict."""
        params_dict = {"params": "bad_value", "api_key": "test-key"}
        params = GenericHangarLLMParams(**params_dict)
        assert params.api_key == "test-key"

    def test_generic_hangarllm_params_with_class_key(self):
        """Test GenericHangarLLMParams handles '__class__' key in input dict."""
        params_dict = {"__class__": "bad_value", "api_key": "test-key"}
        params = GenericHangarLLMParams(**params_dict)
        assert params.api_key == "test-key"

    def test_max_retries_string_conversion(self):
        """Test that max_retries is converted from string to int."""
        params = HangarLLM_Params(model="gpt-4", max_retries="5")
        assert params.max_retries == 5
        assert isinstance(params.max_retries, int)

    def test_extra_fields_preserved(self):
        """Test that extra fields are preserved when reserved keys are filtered."""
        params_dict = {
            "model": "gpt-4",
            "self": "ignored",
            "custom_field": "custom_value",
        }
        params = HangarLLM_Params(**params_dict)
        assert params.model == "gpt-4"
        assert params.custom_field == "custom_value"

    def test_normal_instantiation_still_works(self):
        """Test that normal instantiation without reserved keys works."""
        params = HangarLLM_Params(
            model="gpt-4", api_key="test-key", custom_llm_provider="openai"
        )
        assert params.model == "gpt-4"
        assert params.api_key == "test-key"
        assert params.custom_llm_provider == "openai"

    def test_multiple_reserved_keys(self):
        """Test filtering multiple reserved keys at once."""
        params_dict = {
            "model": "gpt-4",
            "self": "value1",
            "params": "value2",
            "__class__": "value3",
            "api_key": "test-key",
        }
        params = HangarLLM_Params(**params_dict)
        assert params.model == "gpt-4"
        assert params.api_key == "test-key"
