from collections.abc import Mapping, Sequence
from itertools import chain
from pathlib import Path
from typing import Final

SANDBOX_ENTRY: Final = Path(__file__).with_name("sandbox_entry.py")
SYSTEM_PYTHON: Final = "/usr/bin/python3.13"
_READ_ONLY_SYSTEM_DIRS: Final = ("/usr", "/lib", "/bin", "/etc/ssl")
_SCRATCH_BYTES: Final = 64 * 1024 * 1024
_PROXY_URL: Final = "http://127.0.0.1:3128"


def sandbox_environment(env: Mapping[str, str]) -> Mapping[str, str]:
    return {
        **env,
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "HTTPS_PROXY": _PROXY_URL,
        "HTTP_PROXY": _PROXY_URL,
        "https_proxy": _PROXY_URL,
        "http_proxy": _PROXY_URL,
        "NODE_USE_ENV_PROXY": "1",
    }


def bwrap_argv(
    *,
    bwrap: str,
    package_dir: Path,
    egress_socket: Path,
    entry: Sequence[str],
    env: Mapping[str, str],
) -> tuple[str, ...]:
    """A process with its own user, PID, network, IPC and mount namespaces.

    It sees the system directories and its own package read only, a small private /tmp, and one Unix
    socket to the egress proxy. It does not see the runner's files, the gateway, the database or Redis.
    """
    system_binds: Final = tuple(chain.from_iterable(("--ro-bind-try", path, path) for path in _READ_ONLY_SYSTEM_DIRS))
    environment: Final = tuple(
        chain.from_iterable(("--setenv", name, value) for name, value in sandbox_environment(env).items())
    )
    return (
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        *environment,
        *system_binds,
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind",
        str(package_dir),
        str(package_dir),
        "--ro-bind",
        str(SANDBOX_ENTRY),
        "/opt/sandbox_entry.py",
        "--bind",
        str(egress_socket),
        "/run/egress.sock",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--size",
        str(_SCRATCH_BYTES),
        "--tmpfs",
        "/tmp",
        "--chdir",
        "/tmp",
        SYSTEM_PYTHON,
        "/opt/sandbox_entry.py",
        *entry,
    )
