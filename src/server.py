"""Build the FastAPI app: the JSON API, old install routes and the Svelte app.

`main.py` runs it with uvicorn. Tests import `create_app()` through `main.app`.
"""

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from api import register_api
from config import require_app_password
from database_crud import prune_processed_ops
from database_setup import open_database
from pwa_routes import STATIC_DIR, register_pwa_routes
from svelte_frontend import register_svelte_frontend

logger = logging.getLogger(__name__)

# On stop or reload, uvicorn waits this long for open responses, then cancels
# them. Live update streams never end by themselves (src/api/events.py).
SHUTDOWN_TIMEOUT_SECONDS = 1

# Old op results are pruned at startup and then once a day while the server runs.
PRUNE_EVERY_SECONDS = 24 * 60 * 60


def prune_old_ops() -> None:
    """Drop stored API op results older than 30 days; never block startup."""
    try:
        prune_processed_ops()
    except sqlite3.Error:
        logger.exception("Could not prune processed_ops")


async def _prune_daily() -> None:
    while True:
        await asyncio.sleep(PRUNE_EVERY_SECONDS)
        await run_in_threadpool(prune_old_ops)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Open and migrate the database before serving; a failure stops startup.
    open_database()
    prune_old_ops()
    prune = asyncio.create_task(_prune_daily())
    try:
        yield
    finally:
        # Cancel without waiting: a shutdown that waits here logs cancelled streams.
        prune.cancel()


def create_app(build_dir: Path | None = None) -> FastAPI:
    """The whole app. Routes are checked in order, so the Svelte app is last."""
    # The app does not start without an admin password.
    require_app_password()
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    register_api(app)
    register_pwa_routes(app)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # Answers every address no route above matched, so it must come last.
    if build_dir is None:
        register_svelte_frontend(app)
    else:
        register_svelte_frontend(app, build_dir)
    return app
