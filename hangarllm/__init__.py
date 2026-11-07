"""HangarLLM SDK. ``import hangarllm`` is ``import litellm``, submodules included."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType
from typing import Final

_ALIAS: Final = "hangarllm"
_TARGET: Final = "litellm"


class _AliasLoader(importlib.abc.Loader):
    # create_module returns None so the import system stamps the alias spec on a throwaway
    # placeholder, never on the real litellm module that exec_module publishes in its place.
    def __init__(self, target_name: str) -> None:
        self._target_name: Final = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        sys.modules[module.__name__] = importlib.import_module(self._target_name)


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(_ALIAS + "."):
            return None
        target_name: Final = _TARGET + fullname.removeprefix(_ALIAS)
        if importlib.util.find_spec(target_name) is None:
            return None
        return importlib.machinery.ModuleSpec(fullname, _AliasLoader(target_name), is_package=True)


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

import litellm as _litellm  # noqa: E402

sys.modules[_ALIAS] = _litellm
