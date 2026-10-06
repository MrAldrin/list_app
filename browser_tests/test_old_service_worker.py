"""The old app's service worker removes itself when it asks `/sw.js` for an update.

Phones that opened the old (NiceGUI) app still hold its service worker. The
server answers `/sw.js` with a kill switch (src/pwa_routes.py, decision 159).
This test plays the old install: a small stand-in server serves the old worker
at `/sw.js` and a page that registers it, on the port the real server will use
later. Then the real server starts on the same address and the old worker asks
for its update.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from conftest import TestServer
from playwright.sync_api import Error, expect

# The worker the old app served until step 4.3 (src/static/sw.js, unchanged).
OLD_SERVICE_WORKER = """\
const CACHE_NAME = 'listr-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
"""

# What the old pages ran on load.
OLD_PAGE = """\
<!doctype html><title>old app</title><p>old app</p>
<script>
  navigator.serviceWorker.register('/sw.js');
</script>
"""


class OldAppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/sw.js":
            body, kind = OLD_SERVICE_WORKER.encode(), "application/javascript"
        else:
            body, kind = OLD_PAGE.encode(), "text/html"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def registration_count(page) -> int | None:
    """Registered workers, or None while the page is reloading."""
    try:
        return page.evaluate(
            "navigator.serviceWorker.getRegistrations().then((r) => r.length)"
        )
    except Error:
        return None


def test_the_old_service_worker_removes_itself(svelte_build, open_session, tmp_path):
    server = TestServer(tmp_path)
    old_app = ThreadingHTTPServer(("127.0.0.1", server.port), OldAppHandler)
    threading.Thread(target=old_app.serve_forever, daemon=True).start()
    page = open_session("old-install", viewport={"width": 390, "height": 844})
    try:
        page.goto(server.url)
        page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        page.evaluate(
            "caches.open('listr-v1').then((c) => c.put('/old', new Response('x')))"
        )
        assert registration_count(page) == 1
        assert page.evaluate("caches.keys()") == ["listr-v1"]
    finally:
        old_app.shutdown()
        old_app.server_close()

    server.start()
    try:
        # The browser checks `/sw.js` for a changed worker on navigation and on
        # update(); ask now instead of waiting for it.
        page.evaluate(
            "navigator.serviceWorker.getRegistration().then((r) => r.update())"
        )
        deadline = time.monotonic() + 30
        while registration_count(page) != 0:
            assert time.monotonic() < deadline, "the old worker is still registered"
            time.sleep(0.2)

        # The open page was reloaded without a worker and shows the new app.
        expect(page.get_by_label("Room link or code")).to_be_visible()
        assert page.evaluate("navigator.serviceWorker.controller") is None
        assert page.evaluate("caches.keys()") == []
    finally:
        server.stop()
