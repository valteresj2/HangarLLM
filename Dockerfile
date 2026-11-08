# syntax=docker/dockerfile:1.7

# Base image for building
ARG HANGARLLM_BUILD_IMAGE=cgr.dev/chainguard/wolfi-base@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7

# Runtime image
ARG HANGARLLM_RUNTIME_IMAGE=cgr.dev/chainguard/wolfi-base@sha256:360896efb0753a5701c48f860e17130c205eae5a264797aa3e7ea126ee2923a7
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a
# Pinned by digest like the other base images; bump explicitly on Node upgrades.
ARG UI_BUILD_IMAGE=node:24.19-alpine3.24@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43
# Checksum from https://www.pgbouncer.org/downloads/ (the Wolfi repo only carries 1.24.x)
ARG PGBOUNCER_VERSION=1.26.0
ARG PGBOUNCER_SHA256=afd25dd61ee6775d37b40629b87ce08736b3e6955f3057bb212e410fbf21c71d
# Where the admin UI bundle comes from: "ui-builder" compiles ui/hangarllm-dashboard in the image;
# "ui-prebuilt" reuses hangarllm/proxy/_experimental/out from the build context (built on the host
# with `npm run build` + build_ui.sh). BuildKit skips the stage that is not selected.
ARG UI_STAGE=ui-builder

FROM $UV_IMAGE AS uvbin

FROM $HANGARLLM_BUILD_IMAGE AS pgbouncer-builder
ARG PGBOUNCER_VERSION
ARG PGBOUNCER_SHA256
USER root
RUN apk add --no-cache build-base pkgconf libevent-dev openssl-dev curl
WORKDIR /build
RUN curl -fsSL -o pgbouncer.tar.gz "https://www.pgbouncer.org/downloads/files/${PGBOUNCER_VERSION}/pgbouncer-${PGBOUNCER_VERSION}.tar.gz" && \
    echo "${PGBOUNCER_SHA256}  pgbouncer.tar.gz" | sha256sum -c - && \
    tar xzf pgbouncer.tar.gz --strip-components=1 && \
    ./configure --prefix=/usr/local --with-openssl=/usr && \
    make -j"$(nproc)" pgbouncer && \
    install -m 0755 pgbouncer /usr/local/bin/pgbouncer

# Admin UI builder. Pinned to the build platform so the architecture-independent
# Next.js static export compiles once natively even in a multi-arch build,
# instead of once per target arch under QEMU.
FROM --platform=$BUILDPLATFORM $UI_BUILD_IMAGE AS ui-builder

ENV NEXT_TELEMETRY_DISABLED=1 \
    npm_config_fund=false \
    npm_config_audit=false

WORKDIR /ui

COPY ui/hangarllm-dashboard/package.json ui/hangarllm-dashboard/package-lock.json ./
COPY ui/hangarllm-dashboard/vendor/ ./vendor/
RUN --mount=type=cache,target=/root/.npm npm ci --prefer-offline

COPY ui/hangarllm-dashboard/ ./
RUN npm run build

FROM scratch AS ui-prebuilt
COPY hangarllm/proxy/_experimental/out/ /ui/out/

FROM ${UI_STAGE} AS ui-bundle

# Builder stage
FROM $HANGARLLM_BUILD_IMAGE AS builder

WORKDIR /app
USER root

COPY --from=uvbin /uv /usr/local/bin/uv
COPY --from=uvbin /uvx /usr/local/bin/uvx

RUN apk add --no-cache \
    bash \
    gcc \
    python-3.13 \
    python-3.13-dev \
    rust \
    openssl \
    libssl3 \
    openssl-dev \
    nodejs \
    npm \
    libsndfile

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:${PATH}"

# Copy dependency metadata first for layer caching
COPY pyproject.toml uv.lock ./
COPY hangarllm-proxy-extras/pyproject.toml hangarllm-proxy-extras/
COPY packaging/hangarllm-proxy/pyproject.toml packaging/hangarllm-proxy/

# Install third-party dependencies (cached unless pyproject.toml/uv.lock change)
RUN uv sync --frozen --no-install-project --no-install-workspace --no-default-groups --no-editable \
    --extra proxy \
    --extra proxy-runtime \
    --extra extra_proxy \
    --extra semantic-router \
    --extra saml \
    --extra bedrock-realtime \
    --python python3.13

# Copy full source tree
COPY . .

# Replace the committed UI bundle with the one built from this exact source.
# Clearing first drops the committed bundle's content-hashed chunks that COPY
# would otherwise leave behind alongside the fresh ones.
RUN rm -rf hangarllm/proxy/_experimental/out
COPY --from=ui-bundle /ui/out/. hangarllm/proxy/_experimental/out/
RUN mkdir -p /var/lib/hangarllm/ui /var/lib/hangarllm/assets && \
    cp -r /app/hangarllm/proxy/_experimental/out/. /var/lib/hangarllm/ui/ && \
    cp /app/hangarllm/proxy/logo*.png /var/lib/hangarllm/assets/ && \
    touch /var/lib/hangarllm/ui/.hangarllm_ui_ready

# Install project and workspace packages (fast - deps already cached)
RUN uv build --package hangarllm-proxy --wheel --out-dir /wheels
RUN uv sync --frozen --no-install-package hangarllm-proxy --no-default-groups --no-editable \
    --extra proxy \
    --extra proxy-runtime \
    --extra extra_proxy \
    --extra semantic-router \
    --extra saml \
    --extra bedrock-realtime \
    --python python3.13

RUN uv pip install --python /app/.venv/bin/python --no-deps /wheels/hangarllm_proxy-*.whl

RUN HOME=/opt/prisma XDG_CACHE_HOME=/opt/prisma/.cache PRISMA_BINARY_CACHE_DIR=/opt/prisma/binaries \
    npm_config_cache=/root/.npm \
    prisma generate --schema=./schema.prisma

RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh && \
    sed -i 's/\r$//' docker/prod_entrypoint.sh && chmod +x docker/prod_entrypoint.sh

# Runtime stage
FROM $HANGARLLM_RUNTIME_IMAGE AS runtime
ARG HANGARLLM_RELEASE_TAG=""
ENV HANGARLLM_RELEASE_TAG=${HANGARLLM_RELEASE_TAG}

LABEL org.opencontainers.image.title="HangarLLM" \
      org.opencontainers.image.description="HangarLLM, one home for every AI model and agent. Open-source LLM gateway, SDK and admin UI." \
      org.opencontainers.image.licenses="MIT"

USER root

# The base image only configures Chainguard's authenticated apk repo, which
# requires an enterprise subscription. Add the public Wolfi repo so `apk add`
# also works for anyone installing extra packages into a running container.
# upstream issue 33518
RUN echo "https://packages.wolfi.dev/os" >> /etc/apk/repositories

# node (without npm) is required by the prisma CLI at runtime
RUN apk add --no-cache bash openssl libssl3 tzdata nodejs python-3.13 libsndfile libevent
COPY --from=pgbouncer-builder /usr/local/bin/pgbouncer /usr/local/bin/pgbouncer

WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}" \
    PRISMA_BINARY_CACHE_DIR=/opt/prisma/binaries \
    PRISMA_CLI_PATH=/opt/prisma/binaries/node_modules/.bin/prisma \
    PRISMA_CLI_QUERY_ENGINE_TYPE=binary \
    PRISMA_OFFLINE_MODE=true \
    HOME=/app \
    HANGARLLM_NON_ROOT=true

# Copy only what runtime needs. The application is installed inside the venv;
# the rest of the builder's /app is source and build metadata that must not
# ship (manifest-scanning tools attribute everything in it to this image).
# entrypoint.sh invokes hangarllm/proxy/prisma_migration.py by source path.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/docker /app/docker
COPY --from=builder /app/schema.prisma /app/schema.prisma
COPY --from=builder /app/hangarllm/proxy/prisma_migration.py /app/hangarllm/proxy/prisma_migration.py
COPY --from=builder /app/hangarllm-proxy-extras /app/hangarllm-proxy-extras
# Prisma CLI + engines are baked under /opt/prisma, a fixed path every
# runtime uid can read and that no cache volume mount shadows. The paths are
# pinned via PRISMA_BINARY_CACHE_DIR / PRISMA_CLI_PATH and recorded into the
# generated client at build time, so `prisma migrate deploy` on a fresh
# database needs no npm and no network access (#33650, #24554).
COPY --from=builder /opt/prisma /opt/prisma
COPY --from=builder /var/lib/hangarllm/ui /var/lib/hangarllm/ui
COPY --from=builder /var/lib/hangarllm/assets /var/lib/hangarllm/assets

RUN find /app/.venv -type f -path "*/tornado/test/*" -delete && \
    find /app/.venv -type d -path "*/tornado/test" -delete && \
    mkdir -p /nonexistent /app/.cache && \
    PRISMA_PATH=$(python -c "import os, prisma; print(os.path.dirname(prisma.__file__))") && \
    EXTRAS_PATH=$(python -c "import os, hangarllm_proxy_extras; print(os.path.dirname(hangarllm_proxy_extras.__file__))") && \
    chown -R nobody:nogroup /nonexistent /app/.cache /var/lib/hangarllm "$PRISMA_PATH" "$EXTRAS_PATH" && \
    chmod -R a+rX /opt/prisma && \
    test -x /opt/prisma/binaries/node_modules/.bin/prisma && \
    test -f /opt/prisma/binaries/node_modules/prisma/build/index.js && \
    python -c "from prisma.client import BINARY_PATHS; paths = list(BINARY_PATHS.query_engine.values()); assert paths and all(p.startswith('/opt/prisma/') for p in paths), paths"

USER 65534

EXPOSE 4000/tcp

ENTRYPOINT ["docker/prod_entrypoint.sh"]
CMD ["--port", "4000"]
