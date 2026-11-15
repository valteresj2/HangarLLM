# The MCP runner starts local (stdio) MCP servers in bubblewrap sandboxes, away from the gateway.
# Built from the gateway image, provided as the "hangarllm" build context by docker-compose.yml.
FROM hangarllm

USER root
RUN apk add --no-cache bubblewrap npm uv \
    && mkdir -p /var/lib/mcp-runner \
    && chown 65534:65534 /var/lib/mcp-runner

USER 65534
ENV HOME=/var/lib/mcp-runner \
    npm_config_cache=/var/lib/mcp-runner/npm-cache \
    UV_CACHE_DIR=/var/lib/mcp-runner/uv-cache \
    UV_PYTHON_DOWNLOADS=never
EXPOSE 4100/tcp
ENTRYPOINT ["python", "-m", "hangarllm.mcp_runner"]
