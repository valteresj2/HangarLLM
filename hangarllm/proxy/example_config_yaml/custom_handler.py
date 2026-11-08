from typing import Final

import hangarllm
from hangarllm import CustomLLM
from hangarllm.types.utils import ModelResponse


class MyCustomLLM(CustomLLM):
    def completion(self, *args, **kwargs) -> ModelResponse:
        return hangarllm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello world"}],
            mock_response="Hi!",
        )

    async def acompletion(self, *args, **kwargs) -> hangarllm.ModelResponse:
        return hangarllm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello world"}],
            mock_response="Hi!",
        )


my_custom_llm: Final = MyCustomLLM()
