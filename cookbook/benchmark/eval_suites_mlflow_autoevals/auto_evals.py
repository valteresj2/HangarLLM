from dotenv import load_dotenv

load_dotenv()

import hangarllm

from autoevals.llm import *

###################

# hangarllm completion call
question = "which country has the highest population"
response = hangarllm.completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": question}],
)
print(response)
# use the auto eval Factuality() evaluator

print("calling evaluator")
evaluator = Factuality()
result = evaluator(
    output=response.choices[0]["message"][
        "content"
    ],  # response from hangarllm.completion()
    expected="India",  # expected output
    input=question,  # question passed to hangarllm.completion
)

print(result)
