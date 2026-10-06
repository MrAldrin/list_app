"""Serve the built Svelte app (frontend/build/) at the root, /.

The Svelte app is a single-page app: one index.html plus static files. Real
files are served as they are. Any other URL gets index.html, and the router in
the browser picks the page. Register it after every other route: its catch-all
answers whatever no earlier route matched.

Old addresses keep working: the NiceGUI page shapes (/room/{slug},
/list/{slug}, /share/{token}, /create-room/{token}, /admin) are Svelte routes
too, /admin/login goes to /admin, and /app/... (where the app ran during phone
testing) goes to the same address at the root.

The home-screen install manifests are made here too (see
docs/home-screen-installation.md): the same rules as NiceGUI's.
"""

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.convertors import PathConvertor, register_url_convertor

from install_manifest import (
    MANIFEST_CACHE_CONTROL,
    MANIFEST_MEDIA_TYPE,
    manifest_with_start_url,
    room_start_url,
)

logger = logging.getLogger(__name__)

# Set to "true" in the production image: a missing build then stops startup
# instead of serving an app without its frontend.
REQUIRE_BUILD_ENV = "REQUIRE_FRONTEND_BUILD"

# Where the app ran before the switch. Its addresses redirect to the root.
LEGACY_PREFIX = "/app"
# First path parts that belong to the server, never to the Svelte router. The
# catch-all does not match them at all, so an unknown address under them stays
# a real 404 (JSON under /api), and a wrong method stays a 405.
SERVER_PREFIXES = ("api", "static", "_nicegui", "_nicegui_ws", "_room-access")


class _PagePathConvertor(PathConvertor):
    regex = rf"(?!(?:{'|'.join(SERVER_PREFIXES)})(?:/|$)).*"


register_url_convertor("page_path", _PagePathConvertor())

DEFAULT_BUILD_DIR = Path(__file__).resolve().parent.parent / "frontend" / "build"

# Files under _app/immutable/ have a content hash in their name, so a changed
# file always gets a new URL. Everything else must be checked on each load.
IMMUTABLE_PREFIX = "_app/immutable/"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
REVALIDATE_CACHE = "no-cache"


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


def _remove_routes(app: FastAPI, paths: Iterable[str]) -> None:
    """Drop routes that the Svelte app takes over (NiceGUI's pages)."""
    old = set(paths)
    app.router.routes[:] = [
        route for route in app.router.routes if getattr(route, "path", None) not in old
    ]


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


def _manifest_response(start_url: str) -> JSONResponse:
    return JSONResponse(
        manifest_with_start_url(start_url),
        media_type=MANIFEST_MEDIA_TYPE,
        headers={
            "Cache-Control": MANIFEST_CACHE_CONTROL,
            "X-Content-Type-Options": "nosniff",
        },
    )


def register_svelte_frontend(
    app: FastAPI,
    build_dir: Path = DEFAULT_BUILD_DIR,
    replaces: Iterable[str] = (),
) -> bool:
    """Add the routes at the root if a build exists. Return True if added.

    `replaces` lists route paths the Svelte app takes over; they are removed
    from the app, and only when the build exists (without a build the old pages
    stay reachable).
    """
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

    _remove_routes(app, replaces)

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
        # NiceGUI's sign-in page. Svelte's /admin page has the form itself.
        return _redirect(request, "/admin")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def serve_app_manifest() -> JSONResponse:
        # The start page opens the last remembered room.
        return _manifest_response("/")

    @app.get("/room-manifest/{slug}.webmanifest", include_in_schema=False)
    def serve_app_room_manifest(slug: str) -> JSONResponse:
        # Not checked against the database: the Svelte app never tells whether
        # a room exists. An unknown room's icon opens its password prompt.
        return _manifest_response(room_start_url("", slug))

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
        return _file_response(index_file, REVALIDATE_CACHE, INDEX_HEADERS)

    return True
