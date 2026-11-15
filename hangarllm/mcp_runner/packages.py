"""Lock a package once, install exactly the locked files, and find the command it ships.

npm installs run with ``--ignore-scripts`` and uv installs with ``--require-hashes``, so nothing in a
package runs at install time and nothing outside the lock is fetched.
"""

import asyncio
import hashlib
import json
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from hangarllm.mcp_runner.models import PackageRef

_NPM_FLAGS: Final = ("--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error")
_INSTALL_TIMEOUT_SECONDS: Final = 600.0
_JSON_OBJECT: Final = TypeAdapter(dict[str, object])


class PackageError(Exception):
    """A package could not be locked, installed or started."""


@dataclass(frozen=True, slots=True)
class InstalledPackage:
    directory: Path
    entry: tuple[str, ...]


async def _run(argv: Sequence[str], cwd: Path, stdin: bytes | None = None) -> bytes:
    process: Final = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(stdin), timeout=_INSTALL_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        raise PackageError(f"{argv[0]} timed out")
    if process.returncode != 0:
        raise PackageError(f"{argv[0]} failed: {err.decode(errors='replace')[-800:]}")
    return out


def _npm_manifest(package: PackageRef) -> str:
    return json.dumps({"name": "mcp-instance", "private": True, "dependencies": {package.name: package.version}})


def _pip_requirement(package: PackageRef) -> str:
    return f"{package.name}=={package.version}\n"


async def lock_package(package: PackageRef, npm: str, uv: str) -> str:
    with tempfile.TemporaryDirectory(prefix="mcp-lock-") as scratch:
        directory: Final = Path(scratch)
        if package.launcher == "npx":
            (directory / "package.json").write_text(_npm_manifest(package))
            await _run((npm, "install", "--package-lock-only", *_NPM_FLAGS), directory)
            return (directory / "package-lock.json").read_text()
        return (
            await _run(
                (uv, "pip", "compile", "--generate-hashes", "--no-header", "--quiet", "-"),
                directory,
                stdin=_pip_requirement(package).encode(),
            )
        ).decode()


def _npm_bin(package_dir: Path, package: PackageRef) -> Path:
    manifest: Final = _JSON_OBJECT.validate_json(
        (package_dir / "node_modules" / package.name / "package.json").read_text()
    )
    bins: Final = manifest.get("bin")
    unscoped: Final = package.name.rsplit("/", 1)[-1]
    if isinstance(bins, str):
        return package_dir / "node_modules" / package.name / bins
    if isinstance(bins, dict):
        wanted: Final = package.command or (unscoped if unscoped in bins else next(iter(bins), None))
        target: Final = bins.get(wanted) if wanted is not None else None
        if isinstance(target, str):
            return package_dir / "node_modules" / package.name / target
    raise PackageError(f"{package.name} does not declare a command to run")


def _uv_bin(package_dir: Path, package: PackageRef) -> Path:
    command: Final = package_dir / "venv" / "bin" / (package.command or package.name)
    if not command.exists():
        raise PackageError(f"{package.name} does not install a command named {command.name}")
    return command


async def _install_into(directory: Path, package: PackageRef, lock: str, npm: str, uv: str, python: str) -> None:
    if package.launcher == "npx":
        (directory / "package.json").write_text(_npm_manifest(package))
        (directory / "package-lock.json").write_text(lock)
        await _run((npm, "ci", *_NPM_FLAGS), directory)
        return
    (directory / "requirements.txt").write_text(lock)
    await _run((uv, "venv", "--quiet", "--python", python, str(directory / "venv")), directory)
    await _run(
        (
            uv,
            "pip",
            "install",
            "--quiet",
            "--require-hashes",
            "--python",
            str(directory / "venv" / "bin" / "python"),
            "-r",
            "requirements.txt",
        ),
        directory,
    )


class PackageCache:
    """Installed packages keyed by the hash of their lock, so a lock is installed once per runner."""

    def __init__(self, root: Path, npm: str, uv: str, python: str) -> None:
        self._root = root
        self._npm = npm
        self._uv = uv
        self._python = python
        self._locks: dict[str, asyncio.Lock] = {}  # mutable-ok: one install at a time per lock hash

    def _entry(self, directory: Path, package: PackageRef) -> InstalledPackage:
        if package.launcher == "npx":
            return InstalledPackage(directory=directory, entry=("/usr/bin/node", str(_npm_bin(directory, package))))
        return InstalledPackage(directory=directory, entry=(str(_uv_bin(directory, package)),))

    async def install(self, package: PackageRef, lock: str) -> InstalledPackage:
        digest: Final = hashlib.sha256(f"{package.model_dump_json()}\n{lock}".encode()).hexdigest()
        directory: Final = self._root / digest
        install_lock: Final = self._locks.setdefault(digest, asyncio.Lock())
        async with install_lock:
            if not directory.exists():
                self._root.mkdir(parents=True, exist_ok=True)
                staging: Final = Path(tempfile.mkdtemp(prefix=f".{digest[:12]}-", dir=self._root))
                try:
                    await _install_into(staging, package, lock, self._npm, self._uv, self._python)
                    staging.rename(directory)
                except BaseException:
                    shutil.rmtree(staging, ignore_errors=True)
                    raise
        return self._entry(directory, package)
