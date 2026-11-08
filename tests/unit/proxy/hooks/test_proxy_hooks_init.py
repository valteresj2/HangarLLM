"""Regression guard for the enterprise hook registration / import cycle.

Python 3.13 is stricter about partially-initialized modules and surfaces
cycles that Python 3.12 silently tolerated. The previous bug:

  hangarllm.proxy.hooks.__init__
    -> enterprise.enterprise_hooks
    -> hangarllm.hangar.proxy.managed_files
    -> hangarllm.llms.base_llm.managed_resources.isolation
    -> hangarllm.proxy.management_endpoints.common_utils
    -> hangarllm.proxy.utils  (re-enters hangarllm.proxy.hooks mid-init)

silently swallowed the ImportError in `hooks/__init__.py`, leaving
``managed_files`` unregistered and the /files endpoint returning 500.
"""

import pytest

from hangarllm.proxy.hooks import PROXY_HOOKS, get_proxy_hook


def test_managed_files_hook_registered():
    pytest.importorskip("hangarllm.hangar")
    assert "managed_files" in PROXY_HOOKS
    hook_cls = get_proxy_hook("managed_files")
    assert hook_cls.__name__ == "_PROXY_HangarLLMManagedFiles"


def test_managed_vector_stores_hook_registered():
    pytest.importorskip("hangarllm.hangar")
    assert "managed_vector_stores" in PROXY_HOOKS
    hook_cls = get_proxy_hook("managed_vector_stores")
    assert hook_cls.__name__ == "_PROXY_HangarLLMManagedVectorStores"


def test_isolation_module_does_not_pull_in_proxy_utils(monkeypatch):
    """Layering guard: hangarllm.llms.* must not transitively import
    hangarllm.proxy.utils, which would reintroduce the import cycle."""
    import importlib
    import sys

    for mod in [
        "hangarllm.proxy.utils",
        "hangarllm.proxy.management_endpoints.common_utils",
        "hangarllm.llms.base_llm.managed_resources.isolation",
    ]:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    importlib.import_module("hangarllm.llms.base_llm.managed_resources.isolation")
    assert "hangarllm.proxy.utils" not in sys.modules
    assert "hangarllm.proxy.management_endpoints.common_utils" not in sys.modules
