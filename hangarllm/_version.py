from typing import Final

import importlib_metadata


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib_metadata.version(distribution)
    except Exception:
        return None


_legacy_version: Final = _installed_version("hangarllm") or _installed_version("hangarllm")
_core_version: Final = _installed_version("hangarllm-core")

if _legacy_version is not None and _core_version is not None:
    raise RuntimeError(
        "hangarllm and hangarllm-core are both installed and share the hangarllm namespace. "
        "Install them in separate environments."
    )

version = _legacy_version or _core_version or "unknown"
