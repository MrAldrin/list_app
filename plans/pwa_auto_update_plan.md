# PWA Auto-Update Implementation Plan

## Goal
Implement automatic self-updating behavior for the Progressive Web App (PWA) on iOS (Safari) and Android (Chrome, Firefox, Samsung Internet). This eliminates the issue where users currently have to delete and recreate their Home Screen icon whenever new code updates are deployed.

---

## Technical Context & References
- Reference: `plans/pwa_ios_quirks_reference.md` (Explains `/` smart router and PWA scope context).
- Current setup: `manifest.json` exists in `src/static/manifest.json`, registered via `ui.add_head_html()` in `src/main.py`.

---

## Proposed Changes

### 1. New Service Worker Script
**File:** `src/static/sw.js` `[NEW]`

- **Lifecycle:**
  - `install` event: Calls `self.skipWaiting()` to replace old service workers immediately.
  - `activate` event: Calls `self.clients.claim()` so the active service worker controls all client tabs immediately.
- **Fetch Strategy (Network First):**
  - For HTML navigation requests: Always fetch from network first so the latest UI code/HTML is loaded from the backend. Fallback to cache if offline.
  - For static assets (JS/CSS/Icons): Network-first with cache fallback or cache-busting validation.

```javascript
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
```

---

### 2. Service Worker Route & Cache Control Headers
**File:** `src/main.py` `[MODIFY]`

- **Serve `/sw.js` from root scope:**
  Service Workers served from `/static/sw.js` are scoped to `/static/` by default. 
  To allow scope `/`, add a FastAPI route in `main.py`:
  ```python
  from fastapi.responses import FileResponse

  @app.get('/sw.js')
  def serve_service_worker():
      return FileResponse(
          os.path.join(os.path.dirname(__file__), 'static', 'sw.js'),
          media_type='application/javascript',
          headers={'Cache-Control': 'no-cache, no-store, must-revalidate'}
      )
  ```
- **Serve `manifest.json` without aggressive caching:**
  Ensure `/static/manifest.json` also returns `Cache-Control: no-cache` header.

---

### 3. Service Worker Registration in Head HTML
**File:** `src/main.py` `[MODIFY]`

- Inject registration script via `ui.add_head_html()`:
  ```html
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
          .then(reg => {
            // Force SW update check on app open / page load
            reg.update();
          })
          .catch(err => console.error('SW Registration Failed:', err));
      });

      // Also trigger update check when PWA is resumed from background
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.serviceWorker.controller) {
          navigator.serviceWorker.ready.then(reg => reg.update());
        }
      });
    }
  </script>
  ```

---

## Verification Plan

### Manual Testing & Verification
1. **Local Browser Testing:**
   - Launch app via `python src/main.py` (or `uv run python src/main.py`).
   - Open browser developer tools -> **Application** -> **Service Workers**.
   - Verify `/sw.js` is registered with scope `/`.
2. **Auto-Update Behavior Test:**
   - Load app in browser/simulator, confirm Service Worker status.
   - Modify a visible UI text in `src/main.py`.
   - Reload / reopen app tab without clearing cache manually.
   - Verify the UI text updates immediately on network connect.
3. **PWA Standalone Mode Verification:**
   - Check Safari/Chrome PWA behavior via Developer Tools / Mobile device.
   - Ensure `/` smart router still functions correctly as described in `pwa_ios_quirks_reference.md`.

---

## Tracking & Progress
- [x] Create `src/static/sw.js` with Network-First strategy
- [x] Add `/sw.js` route in `src/main.py` with `no-cache` headers
- [x] Register Service Worker and visibility auto-updater in `ui.add_head_html()`
- [x] Test SW registration and update propagation locally
