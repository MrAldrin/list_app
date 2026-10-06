"""Entry point: `uv run src/main.py [--port 8080]` starts the web server.

The server is a plain FastAPI app (src/server.py) run by uvicorn. Importing
this module creates the app, so it checks `APP_PASSWORD` and sets up the
database (migrations run when `database_setup` is imported).
"""

import argparse
import os
from pathlib import Path

import uvicorn

from config import app_reload_enabled
from server import SHUTDOWN_TIMEOUT_SECONDS, create_app

app = create_app()


def parse_port(argv: list[str] | None = None) -> int:
    """`--port`, else `$PORT`, else 8080."""
    parser = argparse.ArgumentParser(description="ListR Web App")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8080")),
        help="Port to run the app on",
    )
    args, _ = parser.parse_known_args(argv)
    return args.port


def run() -> None:
    reload = app_reload_enabled()
    uvicorn.run(
        # Reload needs an import string so the child process can load the app.
        "main:app" if reload else app,
        host="0.0.0.0",
        port=parse_port(),
        reload=reload,
        reload_dirs=[str(Path(__file__).resolve().parent)] if reload else None,
        timeout_graceful_shutdown=SHUTDOWN_TIMEOUT_SECONDS,
        # Warnings only, as before: request logs would hold share links.
        log_level="warning",
    )


if __name__ == "__main__":
    run()
