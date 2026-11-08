"""
Use HangarLLM Proxy MCP Gateway to call MCP tools.

When using HangarLLM Proxy, you can use the same MCP tools across all your LLM providers.
"""

import os

import openai

client = openai.OpenAI(
    api_key=os.environ["HANGARLLM_MASTER_KEY"],
    base_url="http://localhost:4000",  # paste your hangarllm proxy base url here
)
print("Making API request to Responses API with MCP tools")

response = client.responses.create(
    model="gpt-5",
    input=[
        {
            "role": "user",
            "content": "give me TLDR of what valteresj2/HangarLLM repo is about",
            "type": "message",
        }
    ],
    tools=[
        {
            "type": "mcp",
            "server_label": "hangarllm",
            "server_url": "hangarllm_proxy",
            "require_approval": "never",
        }
    ],
    stream=True,
    tool_choice="required",
)

for chunk in response:
    print("response chunk: ", chunk)
