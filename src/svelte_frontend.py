"""Serve the built Svelte app (frontend/build/) at the root, /.

The Svelte app is a single-page app: one index.html plus static files. Real
files are served as they are. Any other URL gets index.html, and the router in
the browser picks the page. Register it after every other route: its catch-all
answers whatever no earlier route matched.

Old addresses keep working: the old page shapes (/room/{slug},
/list/{slug}, /share/{token}, /create-room/{token}, /admin) are Svelte routes
too, /admin/login goes to /admin, and /app/... (where the app ran during phone
testing) goes to the same address at the root.

The home-screen install manifests and the old install addresses are in
src/pwa_routes.py.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.convertors import PathConvertor, register_url_convertor

logger = logging.getLogger(__name__)

# Set to "true" in the production image: a missing build then stops startup
# instead of serving an app without its frontend.
REQUIRE_BUILD_ENV = "REQUIRE_FRONTEND_BUILD"

# Where the app ran before the switch. Its addresses redirect to the root.
LEGACY_PREFIX = "/app"
# First path parts that belong to the server, never to the Svelte router. The
# catch-all does not match them at all, so an unknown address under them stays
# a real 404 (JSON under /api), and a wrong method stays a 405.
SERVER_PREFIXES = ("api", "static")


class _PagePathConvertor(PathConvertor):
    regex = rf"(?!(?:{'|'.join(SERVER_PREFIXES)})(?:/|$)).*"


register_url_convertor("page_path", _PagePathConvertor())

DEFAULT_BUILD_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"

# Files under _app/immutable/ have a content hash in their name, so a changed
# file always gets a new URL. Everything else must be checked on each load.
IMMUTABLE_PREFIX = "_app/immutable/"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
REVALIDATE_CACHE = "no-cache"


# The page shell at the start page and under the room, list and invitation
# addresses is never stored (decision 157): these pages show what the cookies of
# this browser allow. Other page addresses and files only need a check.
NO_STORE_CACHE = "no-store"
NO_STORE_PREFIXES = ("room/", "list/", "create-room/")

# The page itself: links to other sites get no referrer, so share-link and
# invitation addresses do not leak (the meta tag in app.html says the same).
# Not "no-referrer": that also blanks the Origin of our own API writes.
INDEX_HEADERS = {"Referrer-Policy": "same-origin"}


def _file_response(
    path: Path, cache_control: str, extra_headers: dict[str, str] | None = None
) -> FileResponse:
    return FileResponse(
        path,
        headers={
            "Cache-Control": cache_control,
            "X-Content-Type-Options": "nosniff",
            **(extra_headers or {}),
        },
    )


def _redirect(request: Request, path: str) -> RedirectResponse:
    query = request.url.query
    return RedirectResponse(path + (f"?{query}" if query else ""), status_code=308)


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
    """Add the routes at the root if a build exists. Return True if added."""
    build_dir = build_dir.resolve()
    index_file = build_dir / "index.html"
    if not index_file.is_file():
        message = (
            f"Svelte build not found: {index_file}. Run `npm run build` in frontend/."
        )
        if os.environ.get(REQUIRE_BUILD_ENV, "").strip().lower() == "true":
            raise RuntimeError(message)
        logger.warning(message)
        return False

    # Added before the catch-all below, so these win over index.html.
    @app.api_route(LEGACY_PREFIX, methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route(
        LEGACY_PREFIX + "/{path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    def redirect_legacy_app_path(request: Request, path: str = "") -> RedirectResponse:
        # Permanent; the query string stays (for example `?admin=true`).
        return _redirect(request, "/" + path)

    @app.api_route("/admin/login", methods=["GET", "HEAD"], include_in_schema=False)
    def redirect_admin_login(request: Request) -> RedirectResponse:
        # The old sign-in page. The /admin page has the form itself.
        return _redirect(request, "/admin")

    @app.api_route(
        "/{path:page_path}", methods=["GET", "HEAD"], include_in_schema=False
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
        no_store = path == "" or path.startswith(NO_STORE_PREFIXES)
        cache = NO_STORE_CACHE if no_store else REVALIDATE_CACHE
        return _file_response(index_file, cache, INDEX_HEADERS)

    return True
