import os

import uvicorn

from hangarllm.mcp_runner.app import build_app, settings_from_env


def main() -> None:
    uvicorn.run(
        build_app(settings_from_env()),
        host=os.environ.get("HANGARLLM_MCP_RUNNER_HOST", "0.0.0.0"),
        port=int(os.environ.get("HANGARLLM_MCP_RUNNER_PORT", "4100")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
