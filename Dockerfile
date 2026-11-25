# Default target: Bun on Railway. Build --target python for the rollback image.

# Pinned package manager and Vite runtime; Node handles other tool shebangs.
FROM docker.io/oven/bun:1.4.4 AS bun

FROM node:24-slim AS frontend-toolchain
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /build/frontend
COPY frontend/package.json frontend/bun.lock ./
COPY frontend/patches ./patches

FROM frontend-toolchain AS frontend-build
RUN bun install --frozen-lockfile
COPY frontend/ ./
# SvelteKit imports the install manifest and icons shared with Python.
COPY src/static /build/src/static

FROM frontend-build AS static-build
RUN bun run build

FROM frontend-build AS typescript-build
RUN bun run build:ts

# The adapter leaves production packages external to build-ts/.
FROM frontend-toolchain AS typescript-deps
RUN bun install --frozen-lockfile --production --ignore-scripts

# Keep Python's SQLite backup API available to scripts/deploy_backup.py.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS python-runtime
WORKDIR /app

FROM python-runtime AS python
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    REQUIRE_FRONTEND_BUILD=true
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project --no-cache
COPY src/ ./src/
COPY --from=static-build /build/frontend/build ./frontend/build
CMD ["python", "src/main.py"]

FROM python-runtime AS production
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=typescript-deps /build/frontend/package.json ./package.json
COPY --from=typescript-deps /build/frontend/node_modules ./node_modules
COPY --from=typescript-build /build/frontend/build-ts ./build-ts
ENV LISTR_TS_HOST=0.0.0.0 \
    LISTR_TS_PROTOCOL_HEADER=x-forwarded-proto \
    LISTR_TS_HOST_HEADER=x-forwarded-host
HEALTHCHECK --interval=30s --timeout=5s CMD ["bun", "--no-env-file", "-e", "fetch(`http://127.0.0.1:${process.env.PORT || 8080}/healthz`, {redirect: 'error'}).then(r => process.exit(r.status === 200 ? 0 : 1), () => process.exit(1))"]
CMD ["sh", "-c", "LISTR_TS_PORT=\"${PORT:-8080}\" exec bun --no-env-file ./build-ts/index.js"]
