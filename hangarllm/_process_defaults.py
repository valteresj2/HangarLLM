import os
import warnings
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final

import dotenv


def _dev_env_hot_reload_enabled() -> bool:
    """The proxy exports this flag when started with ``--reload``. A reloaded
    worker is a fresh process that inherits the reloader's environment, so an
    edited ``.env`` value stays masked by the stale inherited one unless we
    let the file win; overriding makes the edit take effect on reload."""
    return os.getenv("HANGARLLM_DEV_ENV_HOT_RELOAD") == "True"


_SECRET_FILE_VARIABLES: Final = (
    "HANGARLLM_MASTER_KEY",
    "HANGARLLM_SALT_KEY",
    "HANGARLLM_UI_SESSION_SECRET",
    "HANGARLLM_METRICS_TOKEN",
    "UI_PASSWORD",
    "DATABASE_URL",
    "REDIS_PASSWORD",
)


def _read_secret_file(variable: str, path: str) -> str:
    try:
        with open(path, encoding="utf-8") as secret_file:
            return secret_file.read().strip()
    except OSError as error:
        raise RuntimeError(f"{variable}_FILE points at {path}, which could not be read: {error.strerror}") from error


def secret_file_values(
    environ: Mapping[str, str], read_file: Callable[[str, str], str] = _read_secret_file
) -> Mapping[str, str]:
    """Values for allowlisted secrets given as ``<NAME>_FILE`` (Docker secrets). An explicit ``<NAME>`` wins."""
    return MappingProxyType(
        {
            variable: read_file(variable, environ[f"{variable}_FILE"])
            for variable in _SECRET_FILE_VARIABLES
            if environ.get(f"{variable}_FILE") and not environ.get(variable)
        }
    )


def load_secret_files() -> None:
    os.environ.update(secret_file_values(os.environ))


def apply_process_defaults() -> None:
    load_secret_files()
    warnings.filterwarnings("ignore", message=".*conflict with protected namespace.*")
    # Suppress Pydantic 2.11+ deprecation warning about accessing model_fields on instances
    # This warning can accumulate during streaming and cause memory leaks
    warnings.filterwarnings("ignore", message=".*Accessing the.*attribute on the instance is deprecated.*")
    # ReadOnly on TypedDict fields is repo-wide static discipline (LIT012); pydantic warns it
    # cannot enforce it at runtime, which floods proxy boot once such a type is schema-walked
    warnings.filterwarnings("ignore", message=".*`ReadOnly` qualifier.*")
    if os.getenv("HANGARLLM_MODE", "DEV") == "DEV":
        dotenv.load_dotenv(override=_dev_env_hot_reload_enabled())
        load_secret_files()
