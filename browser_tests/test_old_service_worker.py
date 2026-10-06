"""The retired worker is removed before the Svelte worker saves its shell.

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

# What the old pages ran on.
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


def registration_scripts(page) -> list[str] | None:
    """Registered worker scripts, or None while the page is reloading."""
    try:
        return page.evaluate(
            "navigator.serviceWorker.getRegistrations().then((registrations) => "
            "registrations.flatMap((registration) => "
            "[registration.installing, registration.waiting, registration.active] "
            ".filter(Boolean).map((worker) => new URL(worker.scriptURL).pathname)))"
        )
    except Error:
        return None


def cache_names(page) -> list[str]:
    return page.evaluate("caches.keys()")


def test_the_old_service_worker_is_removed_before_the_new_shell_is_saved(
    svelte_build, open_session, tmp_path
):
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
        assert registration_scripts(page) == ["/sw.js"]
        assert cache_names(page) == ["listr-v1"]
    finally:
        old_app.shutdown()
        old_app.server_close()

    server.start()
    try:
        # The old worker asks for its update. The kill switch removes every
        # cache, unregisters, and reloads the page before the Svelte helper runs.
        page.evaluate(
            "navigator.serviceWorker.getRegistration().then((registration) => registration.update())"
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            scripts = registration_scripts(page) or []
            if "/service-worker.js" in scripts and "/sw.js" not in scripts:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("legacy worker was not replaced by the Svelte worker")
        expect(page.get_by_label("Room link or code")).to_be_visible()

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            names = cache_names(page)
            if any(name.startswith("listr-app-shell-") for name in names):
                break
            time.sleep(0.1)
        else:
            raise AssertionError("the Svelte worker did not save its shell")

        assert "/sw.js" not in registration_scripts(page)
        assert "listr-v1" not in cache_names(page)
        assert len(cache_names(page)) == 1

        # Close the page reloaded by the legacy worker. A fresh page waits for
        # the new worker to activate, then reopens under it without claims.
        context = page.context
        page.close()
        page = context.new_page()
        page.goto(server.url)
        page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        page.close()
        page = context.new_page()
        page.goto(server.url)
        page.wait_for_function(
            "navigator.serviceWorker.controller?.scriptURL.endsWith('/service-worker.js')"
        )
        assert cache_names(page)[0].startswith("listr-app-shell-")

        server.stop()
        page.goto(server.url + "/room/legacy-worker-offline")
        expect(page.get_by_text("Could not load this room.")).to_be_visible()
        assert "/sw.js" not in registration_scripts(page)
    finally:
        server.stop()
