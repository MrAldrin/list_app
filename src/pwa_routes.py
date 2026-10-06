"""Routes for old home-screen installs, icons and the old service worker.

Phones that installed the app before the Svelte switch still point at these
addresses: `/manifest.json`, `/room-manifest/{slug}.json`, the apple-touch icons
and `/favicon.ico`. The new pages link `/manifest.webmanifest` and
`/room-manifest/{slug}.webmanifest` (src/svelte_frontend.py); both pairs answer
with the same content. See docs/home-screen-installation.md.

`/sw.js` is the old app's service worker address. Browsers that still hold the
old worker ask this address for updates. It answers with a script that removes
the old worker and its caches (decision 159). Do not make it 404 or serve HTML:
the old worker would then stay active.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

from install_manifest import (
    MANIFEST_CACHE_CONTROL,
    MANIFEST_MEDIA_TYPE,
    manifest_with_start_url,
    room_start_url,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ICON_DIR = STATIC_DIR / "icons"

# The old worker only cached page loads, so removing it loses no data. It
# deletes every cache, unregisters itself, then reloads open pages so they load
# from the network without a worker. It has no fetch handler.
KILL_SWITCH_SCRIPT = """\
// Retired service worker: removes itself and its caches (src/pwa_routes.py).
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      try {
        const names = await caches.keys();
        await Promise.all(names.map((name) => caches.delete(name)));
      } catch (_) {
        // Caches may be unavailable; unregistering is what matters.
      }
      await self.registration.unregister();
      const windows = await self.clients.matchAll({ type: 'window' });
      for (const client of windows) {
        try {
          client.navigate(client.url);
        } catch (_) {
          // A page that cannot be reloaded keeps working without a worker.
        }
      }
    })()
  );
});
"""


def _manifest_response(start_url: str) -> JSONResponse:
    return JSONResponse(
        manifest_with_start_url(start_url),
        media_type=MANIFEST_MEDIA_TYPE,
        headers={
            "Cache-Control": MANIFEST_CACHE_CONTROL,
            "X-Content-Type-Options": "nosniff",
        },
    )


def register_pwa_routes(app: FastAPI) -> None:
    """Add the old install, icon and service worker routes."""

    @app.get("/sw.js", include_in_schema=False)
    def serve_service_worker_kill_switch() -> Response:
        return Response(
            KILL_SWITCH_SCRIPT,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/manifest.json", include_in_schema=False)
    @app.get("/static/manifest.json", include_in_schema=False)
    def serve_manifest() -> JSONResponse:
        return _manifest_response("/")

    @app.get("/room-manifest/{slug}.json", include_in_schema=False)
    def serve_room_manifest(slug: str) -> JSONResponse:
        # Routing metadata, never proof of access, and no database lookup: the
        # answer does not tell whether a room exists.
        return _manifest_response(room_start_url("", slug))

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def serve_app_manifest() -> JSONResponse:
        # The start page opens the last remembered room.
        return _manifest_response("/")

    @app.get("/room-manifest/{slug}.webmanifest", include_in_schema=False)
    def serve_app_room_manifest(slug: str) -> JSONResponse:
        # An unknown room's icon opens its password prompt.
        return _manifest_response(room_start_url("", slug))

    @app.get("/apple-touch-icon.png", include_in_schema=False)
    @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    def serve_apple_touch_icon() -> FileResponse:
        """Browsers ask for the conventional root icon paths."""
        return FileResponse(ICON_DIR / "apple-touch-icon.png", media_type="image/png")

    @app.get("/favicon.ico", include_in_schema=False)
    def serve_favicon() -> FileResponse:
        return FileResponse(ICON_DIR / "favicon-32.png", media_type="image/png")
