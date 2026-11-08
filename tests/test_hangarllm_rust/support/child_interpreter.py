from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from typing import Final

import hangarllm

PARENT_HANGARLLM_FILE: Final = "HANGARLLM_TEST_PARENT_HANGARLLM_FILE"

_PROLOGUE: Final = (
    "import os as _os, hangarllm as _hangarllm; _parent = _os.environ.pop({key!r}); "
    'assert _hangarllm.__file__ == _parent, f"child imported hangarllm from {{_hangarllm.__file__}}, parent from {{_parent}}"; '
    "del _os, _hangarllm, _parent\n"
)


def run_child_interpreter(
    source: str, *, env: Mapping[str, str] | None = None, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter that imports the same `hangarllm` as this process.

    `-I` keeps the working directory off sys.path so a source checkout cannot shadow an
    installed wheel, and the prologue fails fast with both paths if the child still
    resolves a different package.
    """
    environment: Final = {**(os.environ if env is None else env), PARENT_HANGARLLM_FILE: hangarllm.__file__}
    return subprocess.run(
        [sys.executable, "-I", "-c", _PROLOGUE.format(key=PARENT_HANGARLLM_FILE) + source],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
    )
