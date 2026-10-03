"""Serve the built Svelte app (frontend/build/) under /app/.

The Svelte app is a single-page app: one index.html plus static files. Real
files are served as they are. Any other URL under /app/ gets index.html, and
the router in the browser picks the page.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

BASE_PATH = "/app"
DEFAULT_BUILD_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"

# Files under _app/immutable/ have a content hash in their name, so a changed
# file always gets a new URL. Everything else must be checked on each load.
IMMUTABLE_PREFIX = "_app/immutable/"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
REVALIDATE_CACHE = "no-cache"


def _file_response(path: Path, cache_control: str) -> FileResponse:
    return FileResponse(
        path,
        headers={
            "Cache-Control": cache_control,
            "X-Content-Type-Options": "nosniff",
        },
    )


def _find_file(build_dir: Path, relative_path: str) -> Path | None:
    """Return the file for a URL path, or None if it is not inside build_dir."""
    if not relative_path:
        return None
    try:
        candidate = (build_dir / relative_path).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_relative_to(build_dir) or not candidate.is_file():
        return None
    return candidate


def register_svelte_frontend(app: FastAPI, build_dir: Path = DEFAULT_BUILD_DIR) -> bool:
    """Add the /app/ routes if a build exists. Return True if routes were added."""
    build_dir = build_dir.resolve()
    index_file = build_dir / "index.html"
    if not index_file.is_file():
        return False

    @app.get(BASE_PATH, include_in_schema=False)
    def redirect_to_app(request: Request) -> RedirectResponse:
        query = request.url.query
        return RedirectResponse(f"{BASE_PATH}/" + (f"?{query}" if query else ""))

    @app.api_route(
        BASE_PATH + "/{path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    def serve_svelte_app(path: str) -> Response:
        if "\\" in path or "\x00" in path or ".." in path.split("/"):
            # Never look outside the build folder.
            return Response(status_code=404)
        file = _find_file(build_dir, path)
        if file is not None:
            cache = (
                IMMUTABLE_CACHE
                if path.startswith(IMMUTABLE_PREFIX)
                else REVALIDATE_CACHE
            )
            return _file_response(file, cache)
        if path.startswith("_app/"):
            # A missing build file is a real 404, not a page; serving HTML as
            # JavaScript would only hide the error.
            return Response(status_code=404)
        return _file_response(index_file, REVALIDATE_CACHE)

    return True
