"""Import-time stand-in for the Rust extension ``litellm.rust_bridge._native``.

Unit tests for ``litellm.hangar`` never execute Rust code paths, but importing
``litellm`` touches the extension module. When the compiled module is not
available (e.g. a dev box without a Rust toolchain), install this stub.
"""

import importlib.util
import sys
import types
from unittest.mock import MagicMock


def install() -> None:
    name = "litellm.rust_bridge._native"
    if name in sys.modules:
        return
    try:
        if importlib.util.find_spec(name) is not None:
            return
    except (ImportError, ValueError):
        pass
    stub = types.ModuleType(name)

    def __getattr__(attr: str):  # noqa: N807 - module-level __getattr__
        if attr.startswith("__"):
            raise AttributeError(attr)
        value = MagicMock(name=f"_native.{attr}")
        setattr(stub, attr, value)
        return value

    stub.__getattr__ = __getattr__  # type: ignore[attr-defined]
    sys.modules[name] = stub
