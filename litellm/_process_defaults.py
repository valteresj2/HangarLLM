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
    return os.getenv("LITELLM_DEV_ENV_HOT_RELOAD") == "True"


_HANGARLLM_PREFIX: Final = "HANGARLLM_"
_LITELLM_PREFIX: Final = "LITELLM_"
_PREFIXED_SECRETS: Final = ("MASTER_KEY", "SALT_KEY", "UI_SESSION_SECRET", "METRICS_TOKEN")
_SECRET_FILE_VARIABLES: Final = (
    *(f"{prefix}{name}" for prefix in (_HANGARLLM_PREFIX, _LITELLM_PREFIX) for name in _PREFIXED_SECRETS),
    "UI_PASSWORD",
    "DATABASE_URL",
    "REDIS_PASSWORD",
)


def hangarllm_env_aliases(environ: Mapping[str, str]) -> Mapping[str, str]:
    """``LITELLM_X`` values to set from non-empty ``HANGARLLM_X`` ones. An explicit ``LITELLM_X`` wins."""
    renamed: Final = (
        (_LITELLM_PREFIX + key.removeprefix(_HANGARLLM_PREFIX), value)
        for key, value in environ.items()
        if key.startswith(_HANGARLLM_PREFIX) and value
    )
    return MappingProxyType({target: value for target, value in renamed if target not in environ})


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


def mirror_hangarllm_env() -> None:
    os.environ.update(secret_file_values(os.environ))
    os.environ.update(hangarllm_env_aliases(os.environ))


def apply_process_defaults() -> None:
    mirror_hangarllm_env()
    warnings.filterwarnings("ignore", message=".*conflict with protected namespace.*")
    # Suppress Pydantic 2.11+ deprecation warning about accessing model_fields on instances
    # This warning can accumulate during streaming and cause memory leaks
    warnings.filterwarnings("ignore", message=".*Accessing the.*attribute on the instance is deprecated.*")
    # ReadOnly on TypedDict fields is repo-wide static discipline (LIT012); pydantic warns it
    # cannot enforce it at runtime, which floods proxy boot once such a type is schema-walked
    warnings.filterwarnings("ignore", message=".*`ReadOnly` qualifier.*")
    if os.getenv("LITELLM_MODE", "DEV") == "DEV":
        dotenv.load_dotenv(override=_dev_env_hot_reload_enabled())
        mirror_hangarllm_env()
