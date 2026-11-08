"""Fails when a module under hangarllm/telemetry/ imports any other part of hangarllm."""

import ast
import sys
from collections.abc import Iterator
from itertools import chain
from pathlib import Path
from typing import Final

PACKAGE: Final = "hangarllm.telemetry"
PACKAGE_DIR: Final = Path(__file__).resolve().parents[2] / "hangarllm" / "telemetry"


def _resolved(package: tuple[str, ...], node: ast.ImportFrom) -> Iterator[str]:
    base: Final = package[: len(package) - node.level + 1] if node.level else ()
    if node.module is not None:
        yield ".".join((*base, node.module))
        return
    yield from (".".join((*base, alias.name)) for alias in node.names)


def _imported_modules(tree: ast.AST, package: tuple[str, ...]) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield from ((node.lineno, module) for module in _resolved(package, node))


def _is_forbidden(module: str) -> bool:
    is_hangarllm: Final = module == "hangarllm" or module.startswith("hangarllm.")
    is_own_package: Final = module == PACKAGE or module.startswith(f"{PACKAGE}.")
    return is_hangarllm and not is_own_package


def _violations_in(path: Path, package: tuple[str, ...]) -> Iterator[str]:
    tree: Final = ast.parse(path.read_text(), filename=str(path))
    modules: Final = _imported_modules(tree, package)
    return (f"{path}:{lineno} imports {module}" for lineno, module in modules if _is_forbidden(module))


def find_violations(package_dir: Path) -> tuple[str, ...]:
    root: Final = tuple(PACKAGE.split("."))
    paths: Final = sorted(package_dir.rglob("*.py"))
    return tuple(
        chain.from_iterable(
            _violations_in(path, (*root, *path.relative_to(package_dir).parent.parts)) for path in paths
        )
    )


def main() -> int:
    violations: Final = find_violations(PACKAGE_DIR)
    if not violations:
        sys.stdout.write(f"{PACKAGE} imports nothing else from hangarllm\n")
        return 0
    sys.stderr.write(f"{PACKAGE} must not depend on the rest of hangarllm:\n" + "\n".join(violations) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
