"""Refuse to start when one secret is doing the job of several.

A leaked master key must not also decrypt every stored provider key or open the Admin UI.
"""

import os
from collections.abc import Callable, Mapping
from typing import Final

from litellm.hangar.proxy.ui_session import SESSION_SECRET_ENV_VAR

ALLOW_SHARED_SECRETS_ENV_VAR: Final = "LITELLM_ALLOW_SHARED_SECRETS"
SALT_KEY_ENV_VAR: Final = "LITELLM_SALT_KEY"


class SharedSecretError(Exception):
    pass


def shared_secret_problems(
    *,
    master_key: str | None,
    salt_key: str | None,
    ui_password: str | None,
    session_secret: str | None,
    database_is_configured: bool,
) -> tuple[str, ...]:
    if not master_key:
        return ()
    checks: Final = (
        (database_is_configured and not salt_key, f"{SALT_KEY_ENV_VAR} is not set, so the master key encrypts stored secrets."),
        (salt_key == master_key, f"{SALT_KEY_ENV_VAR} is the same value as the master key."),
        (ui_password == master_key, "UI_PASSWORD is the same value as the master key."),
        (session_secret == master_key, f"{SESSION_SECRET_ENV_VAR} is the same value as the master key."),
    )
    return tuple(message for failed, message in checks if failed)


def render_refusal(problems: tuple[str, ...]) -> str:
    return "\n".join(
        (
            "HangarLLM refused to start because secrets are shared:",
            *(f"  - {problem}" for problem in problems),
            "",
            "Give each one its own random value. python scripts/hangar_init_secrets.py generates them.",
            f"A database already encrypted with the master key must keep {SALT_KEY_ENV_VAR} equal to that key until",
            f"its stored values are re-encrypted. Set {ALLOW_SHARED_SECRETS_ENV_VAR}=true to start in the meantime.",
        )
    )


def enforce_secret_separation(
    *,
    master_key: str | None,
    database_is_configured: bool,
    announce: Callable[[str], object],
    environ: Mapping[str, str] = os.environ,
) -> None:
    if environ.get(ALLOW_SHARED_SECRETS_ENV_VAR, "").strip().lower() == "true":
        return
    problems: Final = shared_secret_problems(
        master_key=master_key,
        salt_key=environ.get(SALT_KEY_ENV_VAR),
        ui_password=environ.get("UI_PASSWORD"),
        session_secret=environ.get(SESSION_SECRET_ENV_VAR),
        database_is_configured=database_is_configured,
    )
    if not problems:
        return
    announce(f"\n{render_refusal(problems)}\n\n")
    raise SharedSecretError("HangarLLM refused to start because secrets are shared. The fix is printed at exit.")
