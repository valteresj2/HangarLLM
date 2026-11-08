"""
hangarllm.interactions.agents

Full CRUD SDK for provider-side managed agents (e.g. Gemini v1beta/agents).

    hangarllm.interactions.agents.create(id=..., ...)
    hangarllm.interactions.agents.list(api_key=...)
    hangarllm.interactions.agents.get(id=..., ...)
    hangarllm.interactions.agents.delete(id=..., ...)
    hangarllm.interactions.agents.list_versions(id=..., ...)

Async counterparts: acreate, alist, aget, adelete, alist_versions
"""

from hangarllm.interactions.agents.main import (
    acreate,
    adelete,
    aget,
    alist,
    alist_versions,
    create,
    delete,
    get,
    list,
    list_versions,
)

__all__ = [
    "acreate",
    "adelete",
    "aget",
    "alist",
    "alist_versions",
    "create",
    "delete",
    "get",
    "list",
    "list_versions",
]
