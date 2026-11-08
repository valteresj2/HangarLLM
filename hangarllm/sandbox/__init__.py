"""hangarllm.sandbox: code-interpreter providers (see main.py) plus harness sandboxes.

`sandbox.local(path)` and `sandbox.docker(image, ...)` re-export hangarllm.harness.sandbox.
They resolve lazily so `import hangarllm` does not pull in hangarllm.harness.
"""

import importlib
from typing import Final

from pydantic import TypeAdapter

_HARNESS_SANDBOX_MODULE: Final = "hangarllm.harness.sandbox"
_HARNESS_EXPORT: Final = TypeAdapter(object)
_HARNESS_EXPORTS: Final = frozenset(
    {
        "local",
        "docker",
        "LocalSandbox",
        "DockerSandbox",
        "Sandbox",
        "Process",
        "CompletedRun",
    }
)


def __getattr__(name: str) -> object:
    if name in _HARNESS_EXPORTS:
        return _HARNESS_EXPORT.validate_python(getattr(importlib.import_module(_HARNESS_SANDBOX_MODULE), name))
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
