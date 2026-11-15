"""Runs inside the mcp-runner container: starts one sandbox with the runner's own code and reports what it can reach.

Usage: ``docker compose cp docker/mcp-runner/verify_sandbox.py mcp-runner:/tmp/`` then
``docker compose exec mcp-runner python /tmp/verify_sandbox.py``. Prints one JSON object, where every reach
except ``allowed_host_via_proxy`` must fail.
"""

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Final

from hangarllm.mcp_runner.egress import EgressProxy, parse_allow_list
from hangarllm.mcp_runner.sandbox import SYSTEM_PYTHON, bwrap_argv

PROBE: Final = r"""
import json, os, socket, ssl, urllib.request

def connect(host, port):
    try:
        socket.create_connection((host, port), timeout=3).close()
        return "connected"
    except Exception as error:
        return type(error).__name__

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status
    except Exception as error:
        return type(error).__name__ + ": " + str(error)[:80]

print(json.dumps({
    "sees_app": os.path.exists("/app"),
    "sees_runner_data": os.path.exists("/var/lib/mcp-runner"),
    "sees_secrets": os.path.exists("/run/secrets"),
    "env_keys": sorted(os.environ),
    "interfaces": [name for _, name in socket.if_nameindex()],
    "gateway": connect("hangarllm", 4000),
    "runner_api": connect("mcp-runner", 4100),
    "postgres": connect("db", 5432),
    "redis": connect("redis", 6379),
    "public_ip_direct": connect("1.1.1.1", 443),
    "allowed_host_via_proxy": fetch("https://example.com/"),
    "unlisted_host_via_proxy": fetch("https://www.wikipedia.org/"),
}))
"""


async def main() -> None:
    work: Final = Path(tempfile.mkdtemp())
    socket_path: Final = work / "egress.sock"
    proxy: Final = EgressProxy("probe", parse_allow_list(("example.com",)))
    server: Final = await proxy.serve(str(socket_path))
    argv: Final = bwrap_argv(
        bwrap=shutil.which("bwrap") or "/usr/bin/bwrap",
        package_dir=work,
        egress_socket=socket_path,
        entry=(SYSTEM_PYTHON, "-c", PROBE),
        env={"MCP_SERVER_SECRET": "only-this-instance"},
    )
    process: Final = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE)
    out, _ = await asyncio.wait_for(process.communicate(), timeout=60)
    server.close()
    report: Final = {"exit_code": process.returncode, **json.loads(out.decode().strip().splitlines()[-1])}
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
