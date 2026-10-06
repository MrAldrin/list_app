# Production image for Railway: builds the Svelte frontend, then runs the app.

# Stage 1: build frontend/build/ (Node is not needed at runtime).
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app. uv installs the locked dependencies.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    REQUIRE_FRONTEND_BUILD=true
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ ./src/
COPY --from=frontend /frontend/build ./frontend/build
CMD ["python", "src/main.py"]
