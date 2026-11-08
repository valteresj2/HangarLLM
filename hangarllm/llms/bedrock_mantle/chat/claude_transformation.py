from hangarllm.llms.base_llm.chat.transformation import BaseConfig
from hangarllm.llms.bedrock.base_aws_llm import BaseAWSLLM
from hangarllm.llms.bedrock.chat.mantle.transformation import AmazonMantleConfig
from hangarllm.llms.bedrock_mantle.chat.transformation import BedrockMantleChatConfig
from hangarllm.llms.bedrock_mantle.common_utils import BedrockMantleAuthMixin, is_mantle_claude_model
from hangarllm.llms.bedrock_mantle.messages.transformation import build_mantle_native_messages_url


class BedrockMantleClaudeChatConfig(BedrockMantleAuthMixin, AmazonMantleConfig):
    def __init__(self, aws_signer: BaseAWSLLM | None = None) -> None:
        AmazonMantleConfig.__init__(self)
        self._aws_signer = aws_signer or self

    @property
    def custom_llm_provider(self) -> str | None:
        return "bedrock_mantle"

    def get_complete_url(
        self,
        api_base: str | None,
        api_key: str | None,
        model: str,
        optional_params: dict[str, object],
        hangarllm_params: dict[str, object],
        stream: bool | None = None,
    ) -> str:
        return build_mantle_native_messages_url(api_base=api_base, hangarllm_params=hangarllm_params)


def bedrock_mantle_chat_config(model: str) -> BaseConfig:
    if is_mantle_claude_model(model):
        return BedrockMantleClaudeChatConfig()
    return BedrockMantleChatConfig()
