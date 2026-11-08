from hangarllm.types.llms.base import HangarLLMBaseModel


class TestPromptRequest(HangarLLMBaseModel):
    dotprompt_content: str
    prompt_variables: dict[str, object] | None = None
    conversation_history: list[dict[str, str]] | None = None
