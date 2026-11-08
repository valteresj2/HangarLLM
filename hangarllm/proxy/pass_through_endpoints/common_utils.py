from typing import Final

from fastapi import Request


def get_hangarllm_virtual_key(request: Request) -> str:
    """
    Extract and format API key from request headers.
    Prioritizes x-hangarllm-api-key over Authorization header.


    Vertex JS SDK uses `Authorization` header, we use `x-hangarllm-api-key` to pass hangarllm virtual key

    """
    hangarllm_api_key: Final = request.headers.get("x-hangarllm-api-key")
    if hangarllm_api_key:
        return f"Bearer {hangarllm_api_key}"
    return request.headers.get("Authorization", "")
