from typing import TYPE_CHECKING

from typing_extensions import ReadOnly, TypedDict

if TYPE_CHECKING:
    from hangarllm.llms.base_llm.videos.transformation import BaseVideoConfig
    from hangarllm.llms.custom_llm import CustomLLM


class CustomLLMItem(TypedDict):
    provider: str
    custom_handler: ReadOnly["CustomLLM | BaseVideoConfig"]
