from typing import Final, Literal

from typing_extensions import NotRequired, ReadOnly, TypedDict

from hangarllm.types.llms.openai import ChatCompletionCachedContent

GATEWAY_INJECTED_CACHE_METADATA_KEY: Final = "hangarllm_gateway_injected_cache"
# No deployment had been chosen when the injection happened, so it is in the payload
# every leg of the request sends. Never a real deployment id.
GATEWAY_INJECTED_FOR_EVERY_DEPLOYMENT: Final = ""


class CacheControlMessageInjectionPoint(TypedDict):
    """Type for message-level injection points."""

    location: Literal["message"]
    role: Literal["user", "system", "assistant"] | None  # Optional: target by role (user, system, assistant)
    index: int | str | None  # Optional: target by specific index
    control: ChatCompletionCachedContent | None
    _hangarllm_openai_dialect: NotRequired[ReadOnly[bool]]
    _hangarllm_external_breakpoints: NotRequired[ReadOnly[int]]
    _hangarllm_custom_llm_provider: NotRequired[ReadOnly[str]]


class CacheControlToolConfigInjectionPoint(TypedDict):
    """Type for tool_config-level injection points (Anthropic and Bedrock)."""

    location: Literal["tool_config"]
    control: ChatCompletionCachedContent | None
    _hangarllm_openai_dialect: NotRequired[ReadOnly[bool]]
    _hangarllm_external_breakpoints: NotRequired[ReadOnly[int]]
    _hangarllm_custom_llm_provider: NotRequired[ReadOnly[str]]


CacheControlInjectionPoint = CacheControlMessageInjectionPoint | CacheControlToolConfigInjectionPoint
