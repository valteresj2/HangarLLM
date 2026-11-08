"""
Handler for transforming /chat/completions api requests to hangarllm.responses requests
"""

from typing import TYPE_CHECKING, Final

from typing_extensions import TypedDict

from hangarllm._internal_context import internal_sub_call

if TYPE_CHECKING:
    from hangarllm import HangarLLMLoggingObj
    from hangarllm.types.llms.openai import HttpxBinaryResponseContent


class SpeechToCompletionBridgeHandlerInputKwargs(TypedDict):
    model: str
    input: str
    voice: str | dict | None
    optional_params: dict
    hangarllm_params: dict
    logging_obj: "HangarLLMLoggingObj"
    headers: dict
    custom_llm_provider: str


class SpeechToCompletionBridgeHandler:
    def __init__(self):
        from .transformation import SpeechToCompletionBridgeTransformationHandler

        super().__init__()
        self.transformation_handler = SpeechToCompletionBridgeTransformationHandler()

    def validate_input_kwargs(self, kwargs: dict) -> SpeechToCompletionBridgeHandlerInputKwargs:
        from hangarllm import HangarLLMLoggingObj

        model: Final = kwargs.get("model")
        if model is None or not isinstance(model, str):
            raise ValueError("model is required")

        custom_llm_provider: Final = kwargs.get("custom_llm_provider")
        if custom_llm_provider is None or not isinstance(custom_llm_provider, str):
            raise ValueError("custom_llm_provider is required")

        input: Final = kwargs.get("input")
        if input is None or not isinstance(input, str):
            raise ValueError("input is required")

        optional_params: Final = kwargs.get("optional_params")
        if optional_params is None or not isinstance(optional_params, dict):
            raise ValueError("optional_params is required")

        hangarllm_params: Final = kwargs.get("hangarllm_params")
        if hangarllm_params is None or not isinstance(hangarllm_params, dict):
            raise ValueError("hangarllm_params is required")

        headers = kwargs.get("headers")
        if headers is None or not isinstance(headers, dict):
            raise ValueError("headers is required")

        headers = kwargs.get("headers")
        if headers is None or not isinstance(headers, dict):
            raise ValueError("headers is required")

        logging_obj: Final = kwargs.get("logging_obj")
        if logging_obj is None or not isinstance(logging_obj, HangarLLMLoggingObj):
            raise ValueError("logging_obj is required")

        return SpeechToCompletionBridgeHandlerInputKwargs(
            model=model,
            input=input,
            voice=kwargs.get("voice"),
            optional_params=optional_params,
            hangarllm_params=hangarllm_params,
            logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider,
            headers=headers,
        )

    def speech(
        self,
        model: str,
        input: str,
        voice: str | dict | None,
        optional_params: dict,
        hangarllm_params: dict,
        headers: dict,
        logging_obj: "HangarLLMLoggingObj",
        custom_llm_provider: str,
    ) -> "HttpxBinaryResponseContent":
        received_args: Final = locals()
        from hangarllm import completion
        from hangarllm.types.utils import ModelResponse

        validated_kwargs: Final = self.validate_input_kwargs(received_args)
        model = validated_kwargs["model"]
        input = validated_kwargs["input"]
        optional_params = validated_kwargs["optional_params"]
        hangarllm_params = validated_kwargs["hangarllm_params"]
        headers = validated_kwargs["headers"]
        logging_obj = validated_kwargs["logging_obj"]
        custom_llm_provider = validated_kwargs["custom_llm_provider"]
        voice = validated_kwargs["voice"]

        request_data: Final = self.transformation_handler.transform_request(
            model=model,
            input=input,
            optional_params=optional_params,
            hangarllm_params=hangarllm_params,
            headers=headers,
            hangarllm_logging_obj=logging_obj,
            custom_llm_provider=custom_llm_provider,
            voice=voice,
        )

        with internal_sub_call(logging_obj.hangarllm_call_id):
            result: Final = completion(
                **request_data,
            )

        requested_response_format: Final = optional_params.get("response_format")
        if isinstance(result, ModelResponse):
            return self.transformation_handler.transform_response(
                model_response=result,
                model=model,
                response_format=requested_response_format if isinstance(requested_response_format, str) else None,
            )
        else:
            raise Exception(f"Unmapped response type. Got type: {type(result)}")


speech_to_completion_bridge_handler = SpeechToCompletionBridgeHandler()
