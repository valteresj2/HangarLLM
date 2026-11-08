#!/usr/bin/env python3
"""Create the Docker secrets used by docker-compose.yml, one file per secret under ./secrets.

Safe to re-run: existing files are kept, because regenerating the salt key makes the provider
credentials stored in the database unreadable. Master and salt keys found in .env are moved into
secrets/ so they stop being visible through `docker inspect`.

Standard library only, so it runs before anything is installed.
"""

import argparse
import re
import secrets
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

GENERATORS: Final[Mapping[str, Callable[[], str]]] = {
    "master_key": lambda: f"sk-{secrets.token_hex(32)}",
    "salt_key": lambda: secrets.token_hex(32),
    "ui_password": lambda: secrets.token_urlsafe(18),
    "ui_session_secret": lambda: secrets.token_hex(32),
    "metrics_token": lambda: secrets.token_hex(32),
    "postgres_password": lambda: secrets.token_hex(24),
    "redis_password": lambda: secrets.token_hex(24),
}
MOVED_FROM_ENV: Final[Mapping[str, tuple[str, ...]]] = {
    "master_key": ("HANGARLLM_MASTER_KEY", "LITELLM_MASTER_KEY"),
    "salt_key": ("HANGARLLM_SALT_KEY", "LITELLM_SALT_KEY"),
    "ui_password": ("UI_PASSWORD",),
}
_ASSIGNMENT: Final = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _parsed(line: str) -> tuple[str, str] | None:
    match: Final = _ASSIGNMENT.match(line)
    return None if match is None else (match.group(1), match.group(2).strip("'\""))


def env_values(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    pairs: Final = (_parsed(line) for line in env_file.read_text(encoding="utf-8").splitlines())
    return {pair[0]: pair[1] for pair in pairs if pair is not None and pair[1]}


def without_moved_secrets(text: str) -> str:
    moved: Final = {name for names in MOVED_FROM_ENV.values() for name in names}
    kept: Final = (line for line in text.splitlines() if (_parsed(line) or ("", ""))[0] not in moved)
    return "\n".join(kept) + "\n"


def _write_secret(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    # The containers run as other uids, so the file is world-readable inside an owner-only directory.
    path.chmod(0o644)


def resolve_secret(name: str, secrets_dir: Path, env: Mapping[str, str]) -> tuple[str, str]:
    """The secret's value and where it came from: existing, env or generated."""
    path: Final = secrets_dir / name
    if path.exists():
        return path.read_text(encoding="utf-8").strip(), "existing"
    from_env: Final = next((env[key] for key in MOVED_FROM_ENV.get(name, ()) if env.get(key)), None)
    value: Final = from_env or GENERATORS[name]()
    _write_secret(path, value)
    return value, "env" if from_env else "generated"


def main() -> None:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("secrets"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args: Final = parser.parse_args()

    args.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.dir.chmod(0o700)
    env: Final = env_values(args.env_file)
    resolved: Final = {name: resolve_secret(name, args.dir, env) for name in GENERATORS}

    database_url: Final = f"postgresql://hangarllm:{resolved['postgres_password'][0]}@db:5432/hangarllm"
    _write_secret(args.dir / "database_url", database_url)
    if args.env_file.exists():
        args.env_file.write_text(without_moved_secrets(args.env_file.read_text(encoding="utf-8")), encoding="utf-8")

    for name, (_, origin) in resolved.items():
        print(f"{name}: {origin}")
    print(f"\nAdmin UI password is in {args.dir / 'ui_password'}. Secret values are never printed here.")
    print("If a Postgres volume already exists, it keeps its old password until you change it with ALTER USER.")


if __name__ == "__main__":
    main()
