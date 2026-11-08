import asyncio
import contextvars
from functools import partial
from typing import TYPE_CHECKING, Any, ClassVar, Final

import httpx
from pydantic import ConfigDict, TypeAdapter

import hangarllm
from hangarllm.constants import request_timeout

# Import the adapter for fallback to completion format
from hangarllm.google_genai.adapters.handler import GenerateContentToCompletionHandler
from hangarllm.hangarllm_core_utils.hangarllm_logging import Logging as HangarLLMLoggingObj
from hangarllm.llms.base_llm.google_genai.transformation import (
    BaseGoogleGenAIGenerateContentConfig,
)
from hangarllm.llms.custom_httpx.llm_http_handler import BaseLLMHTTPHandler
from hangarllm.llms.vertex_ai.vertex_llm_base import VertexBase
from hangarllm.types.llms.base import HangarLLMBaseModel
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.utils import CallTypes
from hangarllm.utils import ProviderConfigManager, client

if TYPE_CHECKING:
    from hangarllm.types.google_genai.main import (
        GenerateContentConfigDict,
        GenerateContentContentListUnionDict,
        GenerateContentResponse,
        ToolConfigDict,
    )
else:
    GenerateContentConfigDict = Any
    GenerateContentContentListUnionDict = Any
    GenerateContentResponse = Any
    ToolConfigDict = Any


####### ENVIRONMENT VARIABLES ###################
# Initialize any necessary instances or variables here
base_llm_http_handler = BaseLLMHTTPHandler()
_GENERATE_CONTENT_RESULT: Final = TypeAdapter(object)
#################################################


def _mark_async_entrypoint(logging_obj: HangarLLMLoggingObj | None, marker: str, is_async: bool) -> None:
    if logging_obj is not None:
        logging_obj.model_call_details.setdefault("hangarllm_params", {})[marker] = is_async


class GenerateContentSetupResult(HangarLLMBaseModel):
    """Internal Type - Result of setting up a generate content call"""

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    model: str
    request_body: dict[str, object]
    custom_llm_provider: str
    generate_content_provider_config: BaseGoogleGenAIGenerateContentConfig | None
    generate_content_config_dict: dict[str, object]
    native_request_fields: dict[str, object]
    hangarllm_params: GenericHangarLLMParams
    hangarllm_logging_obj: HangarLLMLoggingObj
    hangarllm_call_id: str | None


class GenerateContentHelper:
    """Helper class for Google GenAI generate content operations"""

    @staticmethod
    def mock_generate_content_response(
        mock_response: str = "This is a mock response from Google GenAI generate_content.",
    ) -> dict[str, object]:
        """Mock response for generate_content for testing purposes"""
        return {
            "text": mock_response,
            "candidates": [
                {
                    "content": {"parts": [{"text": mock_response}], "role": "model"},
                    "finishReason": "STOP",
                    "index": 0,
                    "safetyRatings": [],
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30,
            },
        }

    @staticmethod
    def setup_generate_content_call(
        model: str,
        contents: GenerateContentContentListUnionDict,
        config: GenerateContentConfigDict | None = None,
        custom_llm_provider: str | None = None,
        tools: ToolConfigDict | None = None,
        **kwargs,
    ) -> GenerateContentSetupResult:
        """
        Common setup logic for generate_content calls

        Args:
            model: The model name
            contents: The content to generate from
            config: Optional configuration
            custom_llm_provider: Optional custom LLM provider
            tools: Optional tools
            **kwargs: Additional keyword arguments

        Returns:
            GenerateContentSetupResult containing all setup information
        """
        hangarllm_logging_obj: Final[HangarLLMLoggingObj | None] = kwargs.get("hangarllm_logging_obj")
        hangarllm_call_id: Final[str | None] = kwargs.get("hangarllm_call_id", None)

        # get llm provider logic
        hangarllm_params: Final = GenericHangarLLMParams(**kwargs)

        ## MOCK RESPONSE LOGIC (only for non-streaming)
        if (
            not kwargs.get("stream", False)
            and hangarllm_params.mock_response
            and isinstance(hangarllm_params.mock_response, str)
        ):
            raise ValueError("Mock response should be handled by caller")

        (
            model,
            custom_llm_provider,
            dynamic_api_key,
            dynamic_api_base,
        ) = hangarllm.get_llm_provider(
            model=model,
            custom_llm_provider=custom_llm_provider,
            api_base=hangarllm_params.api_base,
            api_key=hangarllm_params.api_key,
        )

        if hangarllm_params.custom_llm_provider is None:
            hangarllm_params.custom_llm_provider = custom_llm_provider

        # get provider config
        generate_content_provider_config: Final[BaseGoogleGenAIGenerateContentConfig | None] = (
            ProviderConfigManager.get_provider_google_genai_generate_content_config(
                model=model,
                provider=hangarllm.LlmProviders(custom_llm_provider),
                hangarllm_params=hangarllm_params.model_dump(include={"base_model", "api_base"}),
            )
        )

        if generate_content_provider_config is None:
            # Use adapter to transform to completion format when provider config is None
            # Signal that we should use the adapter by returning special result
            if hangarllm_logging_obj is None:
                raise ValueError("hangarllm_logging_obj is required, but got None")
            return GenerateContentSetupResult(
                model=model,
                custom_llm_provider=custom_llm_provider,
                request_body={},  # Will be handled by adapter
                generate_content_provider_config=None,
                generate_content_config_dict=dict(config or {}),
                native_request_fields={},
                hangarllm_params=hangarllm_params,
                hangarllm_logging_obj=hangarllm_logging_obj,
                hangarllm_call_id=hangarllm_call_id,
            )

        #########################################################################################
        # Construct request body
        #########################################################################################
        # Create Google Optional Params Config
        generate_content_config_dict: Final = generate_content_provider_config.map_generate_content_optional_params(
            generate_content_config_dict=config or {},
            model=model,
        )
        # Extract systemInstruction from kwargs to pass to transform
        system_instruction: Final = kwargs.get("systemInstruction") or kwargs.get("system_instruction")
        # Native top-level REST fields arrive as loose kwargs and are otherwise dropped.
        native_request_fields: Final[dict[str, object]] = {
            field: kwargs[field]
            for field in generate_content_provider_config.get_generate_content_request_top_level_fields()
            if field in kwargs
        }
        request_body: Final = generate_content_provider_config.transform_generate_content_request(
            model=model,
            contents=contents,
            tools=tools,
            generate_content_config_dict=generate_content_config_dict,
            system_instruction=system_instruction,
        )

        # Pre Call logging
        if hangarllm_logging_obj is None:
            raise ValueError("hangarllm_logging_obj is required, but got None")

        vertex_location: Final = VertexBase.explicit_vertex_ai_location(dict(hangarllm_params))
        hangarllm_logging_obj.update_from_kwargs(
            kwargs=kwargs,
            model=model,
            optional_params=dict(generate_content_config_dict),
            hangarllm_params={
                "hangarllm_call_id": hangarllm_call_id,
                **({"vertex_location": vertex_location} if vertex_location else {}),
            },
            custom_llm_provider=custom_llm_provider,
        )

        return GenerateContentSetupResult(
            model=model,
            custom_llm_provider=custom_llm_provider,
            request_body=request_body,
            generate_content_provider_config=generate_content_provider_config,
            generate_content_config_dict=generate_content_config_dict,
            native_request_fields=native_request_fields,
            hangarllm_params=hangarllm_params,
            hangarllm_logging_obj=hangarllm_logging_obj,
            hangarllm_call_id=hangarllm_call_id,
        )


def _merge_native_request_fields(
    native_request_fields: dict[str, object],
    extra_body: dict[str, object] | None,
) -> dict[str, object] | None:
    """
    Merge native top-level request fields into ``extra_body`` so the HTTP handler
    forwards them verbatim onto the outgoing request body. An explicit ``extra_body``
    value wins on conflict. Returns ``None`` only when there is genuinely nothing to
    forward (no native fields and no caller-supplied ``extra_body``), preserving the
    prior behavior without discarding an explicit ``extra_body={}``.
    """
    if not native_request_fields and extra_body is None:
        return None
    return {**native_request_fields, **(extra_body or {})}


@client
async def agenerate_content(
    model: str,
    contents: GenerateContentContentListUnionDict,
    config: GenerateContentConfigDict | None = None,
    tools: ToolConfigDict | None = None,
    # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
    # The extra values given here take precedence over values defined on the client or passed to this method.
    extra_headers: dict[str, object] | None = None,
    extra_query: dict[str, object] | None = None,
    extra_body: dict[str, object] | None = None,
    timeout: float | httpx.Timeout | None = None,
    # HangarLLM specific params,
    custom_llm_provider: str | None = None,
    **kwargs,
) -> object:
    """
    Async: Generate content using Google GenAI
    """
    local_vars: Final = locals()
    try:
        loop: Final = asyncio.get_event_loop()
        kwargs["agenerate_content"] = True

        # Handle generationConfig parameter from kwargs for backward compatibility
        if "generationConfig" in kwargs and config is None:
            config = kwargs.pop("generationConfig")
        # get custom llm provider so we can use this for mapping exceptions
        if custom_llm_provider is None:
            _, custom_llm_provider, _, _ = hangarllm.get_llm_provider(
                model=model,
                custom_llm_provider=custom_llm_provider,
            )

        func: Final = partial(
            generate_content,
            model=model,
            contents=contents,
            config=config,
            extra_headers=extra_headers,
            extra_query=extra_query,
            extra_body=extra_body,
            timeout=timeout,
            custom_llm_provider=custom_llm_provider,
            tools=tools,
            **kwargs,
        )

        ctx: Final = contextvars.copy_context()
        func_with_context: Final = partial(ctx.run, func)
        init_response: Final = await loop.run_in_executor(None, func_with_context)

        if asyncio.iscoroutine(init_response):
            response = _GENERATE_CONTENT_RESULT.validate_python(await init_response)
        else:
            response = init_response

        return response
    except Exception as e:
        raise hangarllm.exception_type(
            model=model,
            custom_llm_provider=custom_llm_provider,
            original_exception=e,
            completion_kwargs=local_vars,
            extra_kwargs=kwargs,
        )


@client
def generate_content(
    model: str,
    contents: GenerateContentContentListUnionDict,
    config: GenerateContentConfigDict | None = None,
    tools: ToolConfigDict | None = None,
    # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
    # The extra values given here take precedence over values defined on the client or passed to this method.
    extra_headers: dict[str, object] | None = None,
    extra_query: dict[str, object] | None = None,
    extra_body: dict[str, object] | None = None,
    timeout: float | httpx.Timeout | None = None,
    # HangarLLM specific params,
    custom_llm_provider: str | None = None,
    **kwargs,
) -> object:
    """
    Generate content using Google GenAI
    """
    local_vars: Final = locals()
    try:
        _is_async: Final = kwargs.pop("agenerate_content", False)

        _mark_async_entrypoint(kwargs.get("hangarllm_logging_obj"), CallTypes.agenerate_content.value, _is_async)

        # Handle generationConfig parameter from kwargs for backward compatibility
        if "generationConfig" in kwargs and config is None:
            config = kwargs.pop("generationConfig")
        # Check for mock response first
        hangarllm_params: Final = GenericHangarLLMParams(**kwargs)
        if hangarllm_params.mock_response and isinstance(hangarllm_params.mock_response, str):
            return GenerateContentHelper.mock_generate_content_response(mock_response=hangarllm_params.mock_response)

        # Setup the call
        setup_result: Final = GenerateContentHelper.setup_generate_content_call(
            model=model,
            contents=contents,
            config=config,
            custom_llm_provider=custom_llm_provider,
            tools=tools,
            **kwargs,
        )

        # Extract systemInstruction from kwargs to pass to handler
        system_instruction: Final = kwargs.get("systemInstruction") or kwargs.get("system_instruction")

        # Check if we should use the adapter (when provider config is None)
        if setup_result.generate_content_provider_config is None:
            # Use the adapter to convert to completion format
            return GenerateContentToCompletionHandler.generate_content_handler(
                model=model,
                contents=contents,
                config=setup_result.generate_content_config_dict,
                tools=tools,
                _is_async=_is_async,
                hangarllm_params=setup_result.hangarllm_params,
                extra_headers=extra_headers,
                **kwargs,
            )

        # Call the standard handler
        response: Final = _GENERATE_CONTENT_RESULT.validate_python(
            base_llm_http_handler.generate_content_handler(
                model=setup_result.model,
                contents=contents,
                tools=tools,
                generate_content_provider_config=setup_result.generate_content_provider_config,
                generate_content_config_dict=setup_result.generate_content_config_dict,
                custom_llm_provider=setup_result.custom_llm_provider,
                hangarllm_params=setup_result.hangarllm_params,
                logging_obj=setup_result.hangarllm_logging_obj,
                extra_headers=extra_headers,
                extra_body=_merge_native_request_fields(setup_result.native_request_fields, extra_body),
                timeout=timeout or request_timeout,
                _is_async=_is_async,
                client=kwargs.get("client"),
                hangarllm_metadata=kwargs.get("hangarllm_metadata", {}),
                system_instruction=system_instruction,
            )
        )

        return response
    except Exception as e:
        raise hangarllm.exception_type(
            model=model,
            custom_llm_provider=custom_llm_provider,
            original_exception=e,
            completion_kwargs=local_vars,
            extra_kwargs=kwargs,
        )


@client
async def agenerate_content_stream(
    model: str,
    contents: GenerateContentContentListUnionDict,
    config: GenerateContentConfigDict | None = None,
    tools: ToolConfigDict | None = None,
    # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
    # The extra values given here take precedence over values defined on the client or passed to this method.
    extra_headers: dict[str, object] | None = None,
    extra_query: dict[str, object] | None = None,
    extra_body: dict[str, object] | None = None,
    timeout: float | httpx.Timeout | None = None,
    # HangarLLM specific params,
    custom_llm_provider: str | None = None,
    **kwargs,
) -> object:
    """
    Async: Generate content using Google GenAI with streaming response
    """
    local_vars: Final = locals()
    try:
        kwargs["agenerate_content_stream"] = True

        _mark_async_entrypoint(kwargs.get("hangarllm_logging_obj"), CallTypes.agenerate_content_stream.value, True)

        # Handle generationConfig parameter from kwargs for backward compatibility
        if "generationConfig" in kwargs and config is None:
            config = kwargs.pop("generationConfig")
        # get custom llm provider so we can use this for mapping exceptions
        if custom_llm_provider is None:
            _, custom_llm_provider, _, _ = hangarllm.get_llm_provider(
                model=model, api_base=local_vars.get("base_url", None)
            )

        # Setup the call
        setup_result: Final = GenerateContentHelper.setup_generate_content_call(
            model=model,
            contents=contents,
            config=config,
            custom_llm_provider=custom_llm_provider,
            tools=tools,
            **kwargs,
        )

        # Extract systemInstruction from kwargs to pass to handler
        system_instruction: Final = kwargs.get("systemInstruction") or kwargs.get("system_instruction")

        # Check if we should use the adapter (when provider config is None)
        if setup_result.generate_content_provider_config is None:
            if "stream" in kwargs:
                kwargs.pop("stream", None)

            # Use the adapter to convert to completion format
            return await GenerateContentToCompletionHandler.async_generate_content_handler(
                model=model,
                contents=contents,
                config=setup_result.generate_content_config_dict,
                hangarllm_params=setup_result.hangarllm_params,
                tools=tools,
                stream=True,
                extra_headers=extra_headers,
                **kwargs,
            )

        # Call the handler with async enabled and streaming
        # Return the coroutine directly for the router to handle
        return _GENERATE_CONTENT_RESULT.validate_python(
            await base_llm_http_handler.generate_content_handler(
                model=setup_result.model,
                contents=contents,
                generate_content_provider_config=setup_result.generate_content_provider_config,
                generate_content_config_dict=setup_result.generate_content_config_dict,
                tools=tools,
                custom_llm_provider=setup_result.custom_llm_provider,
                hangarllm_params=setup_result.hangarllm_params,
                logging_obj=setup_result.hangarllm_logging_obj,
                extra_headers=extra_headers,
                extra_body=_merge_native_request_fields(setup_result.native_request_fields, extra_body),
                timeout=timeout or request_timeout,
                _is_async=True,
                client=kwargs.get("client"),
                stream=True,
                hangarllm_metadata=kwargs.get("hangarllm_metadata", {}),
                system_instruction=system_instruction,
            )
        )

    except Exception as e:
        raise hangarllm.exception_type(
            model=model,
            custom_llm_provider=custom_llm_provider,
            original_exception=e,
            completion_kwargs=local_vars,
            extra_kwargs=kwargs,
        )


@client
def generate_content_stream(
    model: str,
    contents: GenerateContentContentListUnionDict,
    config: GenerateContentConfigDict | None = None,
    tools: ToolConfigDict | None = None,
    # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
    # The extra values given here take precedence over values defined on the client or passed to this method.
    extra_headers: dict[str, object] | None = None,
    extra_query: dict[str, object] | None = None,
    extra_body: dict[str, object] | None = None,
    timeout: float | httpx.Timeout | None = None,
    # HangarLLM specific params,
    custom_llm_provider: str | None = None,
    **kwargs,
) -> object:
    """
    Generate content using Google GenAI with streaming response
    """
    local_vars: Final = locals()
    try:
        # Remove any async-related flags since this is the sync function
        _is_async: Final = kwargs.pop("agenerate_content_stream", False)

        _mark_async_entrypoint(kwargs.get("hangarllm_logging_obj"), CallTypes.agenerate_content_stream.value, _is_async)

        # Handle generationConfig parameter from kwargs for backward compatibility
        if "generationConfig" in kwargs and config is None:
            config = kwargs.pop("generationConfig")
        # Setup the call
        setup_result: Final = GenerateContentHelper.setup_generate_content_call(
            model=model,
            contents=contents,
            config=config,
            custom_llm_provider=custom_llm_provider,
            tools=tools,
            **kwargs,
        )

        # Extract systemInstruction from kwargs to pass to handler
        system_instruction: Final = kwargs.get("systemInstruction") or kwargs.get("system_instruction")

        # Check if we should use the adapter (when provider config is None)
        if setup_result.generate_content_provider_config is None:
            if "stream" in kwargs:
                kwargs.pop("stream", None)

            # Use the adapter to convert to completion format
            return GenerateContentToCompletionHandler.generate_content_handler(
                model=model,
                contents=contents,
                config=setup_result.generate_content_config_dict,
                _is_async=_is_async,
                hangarllm_params=setup_result.hangarllm_params,
                stream=True,
                extra_headers=extra_headers,
                **kwargs,
            )

        # Call the handler with streaming enabled (sync version)
        return _GENERATE_CONTENT_RESULT.validate_python(
            base_llm_http_handler.generate_content_handler(
                model=setup_result.model,
                contents=contents,
                generate_content_provider_config=setup_result.generate_content_provider_config,
                generate_content_config_dict=setup_result.generate_content_config_dict,
                tools=tools,
                custom_llm_provider=setup_result.custom_llm_provider,
                hangarllm_params=setup_result.hangarllm_params,
                logging_obj=setup_result.hangarllm_logging_obj,
                extra_headers=extra_headers,
                extra_body=_merge_native_request_fields(setup_result.native_request_fields, extra_body),
                timeout=timeout or request_timeout,
                _is_async=_is_async,
                client=kwargs.get("client"),
                stream=True,
                hangarllm_metadata=kwargs.get("hangarllm_metadata", {}),
                system_instruction=system_instruction,
            )
        )

    except Exception as e:
        raise hangarllm.exception_type(
            model=model,
            custom_llm_provider=custom_llm_provider,
            original_exception=e,
            completion_kwargs=local_vars,
            extra_kwargs=kwargs,
        )
