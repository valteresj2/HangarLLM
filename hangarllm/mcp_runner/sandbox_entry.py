"""Runs inside the sandbox with the system Python and the standard library only.

The sandbox has a loopback interface and nothing else. This script listens on 127.0.0.1 and relays each
connection to the runner's egress proxy through a bind-mounted Unix socket, then runs the MCP server with
stdin and stdout passed straight through.
"""

import resource
import socket
import subprocess
import sys
import threading

PROXY_PORT = 3128
EGRESS_SOCKET = "/run/egress.sock"


def _pipe(source: socket.socket, target: socket.socket) -> None:
    try:
        while chunk := source.recv(65536):
            target.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            target.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _relay(client: socket.socket) -> None:
    upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        upstream.connect(EGRESS_SOCKET)
    except OSError:
        client.close()
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    _pipe(upstream, client)


def _serve(listener: socket.socket) -> None:
    while True:
        client, _ = listener.accept()
        threading.Thread(target=_relay, args=(client,), daemon=True).start()


def main(argv: list[str]) -> int:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    listener = socket.create_server(("127.0.0.1", PROXY_PORT))
    threading.Thread(target=_serve, args=(listener,), daemon=True).start()
    return subprocess.call(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
