# Production image for Railway: builds the Svelte frontend, then runs the app.

# Pinned package manager and Vite runtime; Node handles other tool shebangs.
FROM docker.io/oven/bun:1.4.4 AS bun

# Build frontend/build/ (Node and Bun are not needed at runtime).
FROM node:24-slim AS frontend
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# The build script forces Vite onto Bun rather than its Node shebang.
RUN bun run build

# Python app. uv installs the locked dependencies.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    REQUIRE_FRONTEND_BUILD=true
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project --no-cache
COPY src/ ./src/
COPY --from=frontend /frontend/build ./frontend/build
CMD ["python", "src/main.py"]
