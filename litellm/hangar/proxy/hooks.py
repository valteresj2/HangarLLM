"""Proxy hooks contributed by HangarLLM (merged into ``litellm.proxy.hooks.PROXY_HOOKS``)."""

from typing import Final

from litellm.hangar.proxy.managed_files import HangarManagedFiles
from litellm.hangar.proxy.managed_vector_stores import HangarManagedVectorStores

HANGAR_PROXY_HOOKS: Final = {
    "managed_files": HangarManagedFiles,
    "managed_vector_stores": HangarManagedVectorStores,
}

# upstream-compatible name
ENTERPRISE_PROXY_HOOKS: Final = HANGAR_PROXY_HOOKS
