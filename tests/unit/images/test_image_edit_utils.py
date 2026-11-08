import asyncio
import base64
import json
from typing import Any, Dict, Final, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import hangarllm
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.images.utils import ImageEditRequestUtils
from hangarllm.hangarllm_core_utils.hangarllm_logging import use_custom_pricing_for_model
from hangarllm.llms.base_llm.image_edit.transformation import BaseImageEditConfig
from hangarllm.types.images.main import ImageEditOptionalRequestParams
from hangarllm.types.utils import StandardLoggingPayload
from hangarllm.utils import ImageResponse

_TEST_IMAGE_BYTES: Final = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


def _make_test_images() -> list[bytes]:
    return [_TEST_IMAGE_BYTES, _TEST_IMAGE_BYTES]


def _make_single_test_image() -> bytes:
    return _TEST_IMAGE_BYTES


class _ImageEditTestLogger(CustomLogger):
    def __init__(self):
        self.standard_logging_payload: Optional[StandardLoggingPayload] = None
        self.logging_completed = asyncio.Event()

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self.standard_logging_payload = kwargs.get("standard_logging_object", None)
        self.logging_completed.set()


class MockImageEditConfig(BaseImageEditConfig):
    def get_supported_openai_params(self, model: str) -> List[str]:
        return ["size", "quality"]

    def map_openai_params(
        self,
        image_edit_optional_params: ImageEditOptionalRequestParams,
        model: str,
        drop_params: bool,
    ) -> Dict[str, Any]:
        return dict(image_edit_optional_params)

    def get_complete_url(self, model: str, api_base: str, hangarllm_params: dict) -> str:
        return "https://example.com/api"

    def validate_environment(
        self,
        headers: dict,
        model: str,
        api_key: Optional[str] = None,
        hangarllm_params: Optional[dict] = None,
        api_base: Optional[str] = None,
    ) -> dict:
        return headers

    def transform_image_edit_request(self, *args, **kwargs):
        return {}, []

    def transform_image_edit_response(self, *args, **kwargs):
        return MagicMock()


class TestImageEditRequestUtilsDropParams:
    def setup_method(self):
        self.config = MockImageEditConfig()
        self.model = "test-model"
        self._original_drop_params = getattr(hangarllm, "drop_params", None)

    def teardown_method(self):
        if self._original_drop_params is None:
            if hasattr(hangarllm, "drop_params"):
                delattr(hangarllm, "drop_params")
        else:
            hangarllm.drop_params = self._original_drop_params

    def test_unsupported_params_raises_without_drop(self):
        hangarllm.drop_params = False
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "unsupported_param": "value",
        }

        with pytest.raises(hangarllm.UnsupportedParamsError) as exc_info:
            ImageEditRequestUtils.get_optional_params_image_edit(
                model=self.model,
                image_edit_provider_config=self.config,
                image_edit_optional_params=optional_params,
            )

        assert "unsupported_param" in str(exc_info.value)

    def test_drop_params_global_setting(self):
        hangarllm.drop_params = True
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "unsupported_param": "value",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
        )

        assert "size" in result
        assert "unsupported_param" not in result

    def test_drop_params_explicit_parameter(self):
        hangarllm.drop_params = False
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "unsupported_param": "value",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
            drop_params=True,
        )

        assert "size" in result
        assert "unsupported_param" not in result

    def test_additional_drop_params(self):
        hangarllm.drop_params = False
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "quality": "high",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
            additional_drop_params=["quality"],
        )

        assert "size" in result
        assert "quality" not in result

    def test_drop_params_false_with_global_true(self):
        hangarllm.drop_params = True
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "unsupported_param": "value",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
            drop_params=False,
        )

        assert "size" in result
        assert "unsupported_param" not in result

    def test_supported_params_pass_through(self):
        hangarllm.drop_params = False
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "quality": "high",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
        )

        assert result["size"] == "1024x1024"
        assert result["quality"] == "high"

    def test_additional_drop_params_with_unsupported_and_drop_true(self):
        hangarllm.drop_params = True
        optional_params: ImageEditOptionalRequestParams = {
            "size": "1024x1024",
            "quality": "high",
            "unsupported_param": "value",
        }

        result = ImageEditRequestUtils.get_optional_params_image_edit(
            model=self.model,
            image_edit_provider_config=self.config,
            image_edit_optional_params=optional_params,
            additional_drop_params=["quality"],
        )

        assert "size" in result
        assert "quality" not in result
        assert "unsupported_param" not in result


class TestImageEditCustomPricing:
    """
    Regression tests for upstream issue 22244

    image_edit must forward model_info and metadata into hangarllm_params
    when calling update_environment_variables, so that custom pricing
    detection works after PR #20679 stripped custom pricing fields from
    the shared backend model key.
    """

    def test_image_edit_passes_model_info_to_logging(self):
        """
        When the router provides model_info with custom pricing fields,
        image_edit should include model_info and metadata in hangarllm_params.
        """
        from hangarllm.images.main import image_edit

        custom_model_info = {
            "id": "test-deployment-id",
            "input_cost_per_image": 0.00676128,
            "mode": "image_generation",
        }
        custom_metadata = {
            "model_info": custom_model_info,
        }

        captured_hangarllm_params = {}

        mock_logging_obj = MagicMock()
        mock_logging_obj.model_call_details = {}

        original_update = mock_logging_obj.update_from_kwargs

        def capturing_update(**update_kwargs):
            captured_hangarllm_params.update(update_kwargs.get("hangarllm_params", {}))
            inner_kwargs = update_kwargs.get("kwargs", {})
            if "metadata" in inner_kwargs:
                captured_hangarllm_params["metadata"] = inner_kwargs["metadata"]
            return original_update(**update_kwargs)

        mock_logging_obj.update_from_kwargs = capturing_update

        with (
            patch(
                "hangarllm.images.main.get_llm_provider",
                return_value=("test-model", "openai", None, None),
            ),
            patch(
                "hangarllm.images.main.ProviderConfigManager.get_provider_image_edit_config",
                return_value=MagicMock(),
            ),
            patch(
                "hangarllm.images.main._get_ImageEditRequestUtils",
                return_value=MagicMock(
                    get_requested_image_edit_optional_param=MagicMock(return_value={}),
                    get_optional_params_image_edit=MagicMock(return_value={}),
                ),
            ),
            patch("hangarllm.images.main.base_llm_http_handler") as mock_handler,
        ):
            mock_handler.image_edit_handler.return_value = MagicMock()

            try:
                image_edit(
                    image=b"fake-image-data",
                    prompt="test prompt",
                    model="openai/test-model",
                    hangarllm_logging_obj=mock_logging_obj,
                    model_info=custom_model_info,
                    metadata=custom_metadata,
                )
            except Exception:
                pass

        assert "model_info" in captured_hangarllm_params
        assert captured_hangarllm_params["model_info"] == custom_model_info
        assert "metadata" in captured_hangarllm_params
        assert captured_hangarllm_params["metadata"] == custom_metadata

    def test_custom_pricing_detected_from_model_info_in_metadata(self):
        hangarllm_params = {
            "metadata": {
                "model_info": {
                    "id": "deployment-id",
                    "input_cost_per_image": 0.00676128,
                },
            },
        }
        assert use_custom_pricing_for_model(hangarllm_params) is True

    def test_custom_pricing_not_detected_without_model_info(self):
        hangarllm_params = {"hangarllm_call_id": "test-call-id"}
        assert use_custom_pricing_for_model(hangarllm_params) is False


class TestImageEditHandlerCredentialsForwarding:
    """
    Regression tests for Vertex AI image_edit credentials bug.

    image_edit handler must forward hangarllm_params to validate_environment,
    so that credentials passed via YAML config (vertex_ai_project,
    vertex_ai_credentials, etc.) reach the auth layer instead of falling
    through to Application Default Credentials.
    """

    def test_vertex_gemini_image_edit_reads_credentials_from_hangarllm_params(self):
        """
        VertexAIGeminiImageEditConfig.validate_environment should read
        vertex_ai_project/vertex_ai_credentials from hangarllm_params first.
        """
        from hangarllm.llms.vertex_ai.image_edit.vertex_gemini_transformation import (
            VertexAIGeminiImageEditConfig,
        )

        config = VertexAIGeminiImageEditConfig()

        hangarllm_params = {
            "vertex_ai_project": "test-project-from-params",
            "vertex_ai_credentials": "/path/to/creds.json",
        }

        with patch.object(
            config, "_ensure_access_token", return_value=("token", "project")
        ) as mock_ensure:
            config.validate_environment(
                headers={},
                model="test-model",
                hangarllm_params=hangarllm_params,
            )

            mock_ensure.assert_called_once()
            call_kwargs = mock_ensure.call_args[1]

            assert call_kwargs["credentials"] == "/path/to/creds.json"
            assert call_kwargs["project_id"] == "test-project-from-params"

    def test_vertex_imagen_image_edit_reads_credentials_from_hangarllm_params(self):
        """
        VertexAIImagenImageEditConfig.validate_environment should read
        vertex_ai_project/vertex_ai_credentials from hangarllm_params first.
        """
        from hangarllm.llms.vertex_ai.image_edit.vertex_imagen_transformation import (
            VertexAIImagenImageEditConfig,
        )

        config = VertexAIImagenImageEditConfig()

        hangarllm_params = {
            "vertex_ai_project": "test-project-from-params",
            "vertex_ai_credentials": "/path/to/creds.json",
        }

        with patch.object(
            config, "_ensure_access_token", return_value=("token", "project")
        ) as mock_ensure:
            config.validate_environment(
                headers={},
                model="test-model",
                hangarllm_params=hangarllm_params,
            )

            mock_ensure.assert_called_once()
            call_kwargs = mock_ensure.call_args[1]

            assert call_kwargs["credentials"] == "/path/to/creds.json"
            assert call_kwargs["project_id"] == "test-project-from-params"

    def test_vertex_imagen_get_complete_url_reads_project_and_location_from_hangarllm_params(
        self,
    ):
        """
        VertexAIImagenImageEditConfig.get_complete_url should read
        vertex_ai_project and vertex_ai_location from hangarllm_params,
        not only from env vars / global settings.
        """
        from hangarllm.llms.vertex_ai.image_edit.vertex_imagen_transformation import (
            VertexAIImagenImageEditConfig,
        )

        config = VertexAIImagenImageEditConfig()

        hangarllm_params = {
            "vertex_ai_project": "param-project",
            "vertex_ai_location": "us-east1",
        }

        url = config.get_complete_url(
            model="vertex_ai/imagegeneration@002",
            api_base=None,
            hangarllm_params=hangarllm_params,
        )

        assert "param-project" in url
        assert "us-east1" in url

    def test_validate_environment_signature_includes_hangarllm_params(self):
        """
        All image_edit config validate_environment methods should accept
        hangarllm_params to allow credentials to be forwarded from the handler.
        """
        import inspect

        from hangarllm.llms.vertex_ai.image_edit.vertex_gemini_transformation import (
            VertexAIGeminiImageEditConfig,
        )
        from hangarllm.llms.vertex_ai.image_edit.vertex_imagen_transformation import (
            VertexAIImagenImageEditConfig,
        )
        from hangarllm.llms.openai.image_edit.transformation import (
            OpenAIImageEditConfig,
        )

        configs = [
            VertexAIGeminiImageEditConfig(),
            VertexAIImagenImageEditConfig(),
            OpenAIImageEditConfig(),
            MockImageEditConfig(),
        ]

        for config in configs:
            sig = inspect.signature(config.validate_environment)
            params = list(sig.parameters.keys())

            assert "hangarllm_params" in params, (
                f"{config.__class__.__name__}.validate_environment "
                "missing hangarllm_params parameter"
            )
            assert "api_base" in params, (
                f"{config.__class__.__name__}.validate_environment "
                "missing api_base parameter"
            )


@pytest.mark.asyncio
async def test_azure_image_edit_hangarllm_sdk():
    """Test Azure image edit with mocked httpx request to validate request body and URL"""
    from hangarllm import aimage_edit

    # Mock response for Azure image edit
    mock_response = {
        "created": 1589478378,
        "data": [
            {
                "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            }
        ],
    }

    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code
            self.text = json.dumps(json_data)
            self.headers = {}

        def json(self):
            return self._json_data

    with patch(
        "hangarllm.llms.custom_httpx.http_handler.AsyncHTTPHandler.post",
        new_callable=AsyncMock,
    ) as mock_post:
        # Configure the mock to return our response
        mock_post.return_value = MockResponse(mock_response, 200)

        hangarllm.turn_on_debug()

        prompt = """
        Create a studio ghibli style image that combines all the reference images. Make sure the person looks like a CTO.
        """

        # Set up test environment variables
        test_api_base = "https://ai-api-gw-uae-north.openai.azure.com"
        test_api_key = "test-api-key"
        test_api_version = "2025-04-01-preview"

        result = await aimage_edit(
            prompt=prompt,
            model="azure/gpt-image-1",
            api_base=test_api_base,
            api_key=test_api_key,
            api_version=test_api_version,
            image=_make_test_images(),
        )

        # Verify the request was made correctly
        mock_post.assert_called_once()

        # Check the URL
        call_args = mock_post.call_args
        expected_url = f"{test_api_base}/openai/deployments/gpt-image-1/images/edits?api-version={test_api_version}"
        actual_url = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        )
        print(f"Expected URL: {expected_url}")
        print(f"Actual URL: {actual_url}")
        assert (
            actual_url == expected_url
        ), f"URL mismatch. Expected: {expected_url}, Got: {actual_url}"

        # Check the request body
        if "data" in call_args.kwargs:
            # For multipart form data, check the data parameter
            form_data = call_args.kwargs["data"]
            print(
                "Form data keys:",
                list(form_data.keys()) if hasattr(form_data, "keys") else "Not a dict",
            )

            # Deployment is in the URL path; Azure rejects model in multipart for this route.
            assert (
                "model" not in form_data
            ), "model must not be in form data for Azure /openai/deployments/.../images/edits"
            assert "prompt" in form_data, "prompt should be in the form data"
            assert (
                prompt.strip() in form_data["prompt"]
            ), f"Expected prompt to contain '{prompt.strip()}'"

        # Check headers
        headers = call_args.kwargs.get("headers", {})
        print("Request headers:", headers)
        assert (
            "api-key" in headers
        ), "Azure image edit must use the api-key header, not Authorization: Bearer"
        assert headers["api-key"] == test_api_key
        assert (
            "Authorization" not in headers
        ), "Azure image edit must not send an Authorization header when an api_key is provided"

        print("result from image edit", result)

        # Validate the response meets expected schema
        ImageResponse.model_validate(result)

@pytest.mark.asyncio
async def test_openai_image_edit_cost_tracking():
    """Test OpenAI image edit cost tracking with custom logger"""
    from hangarllm import aimage_edit, image_edit

    test_custom_logger = TestCustomLogger()
    hangarllm.logging_callback_manager._reset_all_callbacks()
    hangarllm.callbacks = [test_custom_logger]

    # Mock response for Azure image edit with usage data for cost tracking
    mock_response = {
        "created": 1589478378,
        "data": [
            {
                "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            }
        ],
        "usage": {
            "total_tokens": 1100,
            "input_tokens": 100,
            "input_tokens_details": {"image_tokens": 50, "text_tokens": 50},
            "output_tokens": 1000,
        },
    }

    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code
            self.text = json.dumps(json_data)
            self.headers = {}

        def json(self):
            return self._json_data

    with patch(
        "hangarllm.llms.custom_httpx.http_handler.AsyncHTTPHandler.post",
        new_callable=AsyncMock,
    ) as mock_post:
        # Configure the mock to return our response
        mock_post.return_value = MockResponse(mock_response, 200)

        hangarllm.turn_on_debug()

        prompt = """
        Create a studio ghibli style image that combines all the reference images. Make sure the person looks like a CTO.
        """

        # Set up test environment variables

        result = await aimage_edit(
            prompt=prompt,
            model="openai/gpt-image-1",
            image=_make_test_images(),
        )

        # Verify the request was made correctly
        mock_post.assert_called_once()

        # Validate the response meets expected schema
        ImageResponse.model_validate(result)

        await asyncio.sleep(5)
        print(
            "standard logging payload",
            json.dumps(
                test_custom_logger.standard_logging_payload, indent=4, default=str
            ),
        )

        # check model
        assert test_custom_logger.standard_logging_payload["model"] == "gpt-image-1"
        assert (
            test_custom_logger.standard_logging_payload["custom_llm_provider"]
            == "openai"
        )

        # check response_cost
        assert test_custom_logger.standard_logging_payload["response_cost"] is not None
        assert test_custom_logger.standard_logging_payload["response_cost"] > 0


def test_recraft_image_edit_config():
    """
    Test Recraft image edit configuration parameter mapping and request transformation.
    """
    from hangarllm.llms.recraft.image_edit.transformation import RecraftImageEditConfig
    from hangarllm.types.images.main import ImageEditOptionalRequestParams
    from hangarllm.types.router import GenericHangarLLMParams

    config = RecraftImageEditConfig()

    supported_params = config.get_supported_openai_params("recraftv3")
    expected_params = ["n", "response_format", "style"]
    assert supported_params == expected_params

    image_edit_params = ImageEditOptionalRequestParams(
        {
            "n": 2,
            "response_format": "b64_json",
            "style": "realistic_image",
            "size": "1024x1024",
            "quality": "high",
        }
    )

    mapped_params = config.map_openai_params(
        image_edit_params, "recraftv3", drop_params=True
    )

    assert mapped_params["n"] == 2
    assert mapped_params["response_format"] == "b64_json"
    assert mapped_params["style"] == "realistic_image"
    assert "size" not in mapped_params
    assert "quality" not in mapped_params

    mock_image = b"fake_image_data"
    prompt = "winter landscape"
    hangarllm_params = GenericHangarLLMParams(api_key="test_key")

    data, files = config.transform_image_edit_request(
        model="recraftv3",
        prompt=prompt,
        image=mock_image,
        image_edit_optional_request_params={"strength": 0.7, "n": 1},
        hangarllm_params=hangarllm_params,
        headers={},
    )

    assert data["prompt"] == prompt
    assert data["strength"] == 0.7
    assert data["model"] == "recraftv3"

    assert len(files) == 1
    assert files[0][0] == "image"
    assert files[0][1][1] == mock_image
    assert files[0][1][2] == "image/png"


@pytest.mark.flaky(retries=3, delay=2)
@pytest.mark.asyncio
async def test_image_edit_array_handling():
    """Test that the image parameter correctly handles both single items and arrays"""
    from hangarllm import aimage_edit

    mock_response = {
        "created": 1589478378,
        "data": [
            {
                "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            }
        ],
    }

    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json_data = json_data
            self.status_code = status_code
            self.text = json.dumps(json_data)
            self.headers = {}

        def json(self):
            return self._json_data

    with patch(
        "hangarllm.llms.custom_httpx.http_handler.AsyncHTTPHandler.post",
        new_callable=AsyncMock,
    ) as mock_post:
        mock_post.return_value = MockResponse(mock_response, 200)

        prompt = "Test prompt"

        result1 = await aimage_edit(
            prompt=prompt,
            model="gpt-image-1",
            image=_make_single_test_image(),
        )

        result2 = await aimage_edit(
            prompt=prompt,
            model="gpt-image-1",
            image=_make_test_images(),
        )

        ImageResponse.model_validate(result1)
        ImageResponse.model_validate(result2)

        assert mock_post.call_count == 2


class TestCustomLogger(CustomLogger):
    def __init__(self):
        self.standard_logging_payload: Optional[StandardLoggingPayload] = None

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self.standard_logging_payload = kwargs.get("standard_logging_object", None)
        pass
