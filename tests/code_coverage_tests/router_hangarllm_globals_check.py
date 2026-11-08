"""
The router and its cores never read or write ``hangarllm.*``.

Process settings reach the router through ``RouterDynamicConfig`` (hangarllm/router_config.py) and
everything else outside it (inference calls, callbacks, the global cache) through ``PythonHost``
(hangarllm/router_python_host.py). Those two modules are the only router code allowed to touch the
``hangarllm`` package namespace. This check fails on ``import hangarllm`` (or ``import hangarllm.<x>``,
which binds the same name) and on any ``hangarllm.<attr>`` access in the files below.

Run: python tests/code_coverage_tests/router_hangarllm_globals_check.py
"""

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHECKED = (
    "hangarllm/router.py",
    "hangarllm/router_api.py",
    "hangarllm/router_core.py",
    "hangarllm/router_deprecated.py",
    "hangarllm/router_rust/core.py",
)


def violations(rel: str) -> list[str]:
    tree = ast.parse(open(os.path.join(ROOT, rel)).read(), rel)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                f"{rel}:{node.lineno}: import {alias.name}"
                for alias in node.names
                if alias.asname is None and (alias.name == "hangarllm" or alias.name.startswith("hangarllm."))
            )
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "hangarllm":
            found.append(f"{rel}:{node.lineno}: hangarllm.{node.attr}")
    return found


def main() -> int:
    found = [line for rel in CHECKED for line in violations(rel)]
    for line in found:
        print(line)
    if found:
        print(f"{len(found)} hangarllm.* uses in router modules; read settings from RouterDynamicConfig and use PythonHost")
        return 1
    print("router modules use no hangarllm.* globals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
