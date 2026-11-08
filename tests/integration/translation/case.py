from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue


@dataclass(frozen=True, slots=True, kw_only=True)
class TranslationTestCase:
    """One request through the proxy to a deployment in `proxy_config.yaml`: what the test sends to HangarLLM, the
    exact request the provider must receive, the fake provider's status and reply, and the exact response HangarLLM must
    return."""

    scenario: str
    hangarllm_endpoint: str
    hangarllm_request: Mapping[str, JsonValue]
    expected_provider_endpoint: str
    expected_provider_headers: Mapping[str, str]
    expected_provider_request: Mapping[str, JsonValue]
    mock_provider_status_code: int = 200
    mock_provider_response: Mapping[str, JsonValue]
    expected_hangarllm_status_code: int = 200
    expected_hangarllm_response: Mapping[str, JsonValue]

    @property
    def id(self) -> str:
        return f"{self.hangarllm_request['model']}-{self.scenario}"


@dataclass(frozen=True, slots=True, kw_only=True)
class SSEFrame:
    data: Mapping[str, JsonValue] | Literal["[DONE]"]
    event: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EventStreamFrame:
    data: Mapping[str, JsonValue]
    headers: Mapping[str, str | int]


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamingTranslationTestCase:
    """Provider frames with optional exact responses or independently expected message and usage values."""

    scenario: str
    hangarllm_endpoint: str
    hangarllm_request: Mapping[str, JsonValue]
    expected_provider_endpoint: str
    expected_provider_headers: Mapping[str, str]
    expected_provider_request: Mapping[str, JsonValue]
    mock_provider_frames: tuple[SSEFrame | EventStreamFrame, ...]
    expected_hangarllm_frames: tuple[SSEFrame, ...] | None = None
    expected_hangarllm_response: Mapping[str, JsonValue] | None = None
    expected_hangarllm_message: Mapping[str, JsonValue] | None = None
    expected_hangarllm_usage: Mapping[str, JsonValue] | None = None

    @property
    def id(self) -> str:
        return f"{self.hangarllm_request['model']}-{self.scenario}"
