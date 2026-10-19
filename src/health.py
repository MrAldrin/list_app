"""GET /healthz: is the app up and can it read the database? For Railway.

No login and no data: the answer is only ok or not. It is registered before
the Svelte catch-all (src/svelte_frontend.py), so it is never answered with
the app page.
"""

import logging
import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from database_crud import transaction
from database_setup import db

logger = logging.getLogger(__name__)


def register_health_route(app: FastAPI) -> None:
    @app.get("/healthz", include_in_schema=False)
    def healthz() -> JSONResponse:
        # A plain def route: FastAPI runs it in a worker thread, so waiting for
        # the database lock does not block the event loop.
        try:
            with transaction():
                db.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            logger.exception("Health check: the database did not answer")
            return JSONResponse(
                {"ok": False}, status_code=503, headers={"Cache-Control": "no-store"}
            )
        return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
