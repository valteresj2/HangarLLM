"""Proxy hooks contributed by HangarLLM (merged into ``hangarllm.proxy.hooks.PROXY_HOOKS``)."""

from typing import Final

from hangarllm.hangar.proxy.managed_files import HangarManagedFiles
from hangarllm.hangar.proxy.managed_vector_stores import HangarManagedVectorStores

HANGAR_PROXY_HOOKS: Final = {
    "managed_files": HangarManagedFiles,
    "managed_vector_stores": HangarManagedVectorStores,
}

# upstream-compatible name
ENTERPRISE_PROXY_HOOKS: Final = HANGAR_PROXY_HOOKS
