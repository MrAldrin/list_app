# Plan: Making ListR a Progressive Web App (PWA)

To make ListR feel like a native app on mobile (bookmarkable to home screen), we will implement PWA features.

## Proposed Changes

1.  **Add PWA Assets:**
    *   Create a `manifest.json` file to tell the browser how the app should behave when "installed".
    *   Add a simple SVG icon as a placeholder for the app icon.
2.  **Configure NiceGUI to serve PWA assets:**
    *   Expose the `static` folder to serve the manifest and icon.
    *   Inject the necessary `<meta>` and `<link>` tags into the HTML `<head>` for both Android and iOS support.

## Detailed Steps

### 1. Create PWA assets in `src/static/`
*   `manifest.json`: Defines app name, start URL, display mode (standalone), and icons.
*   `icon.svg`: A simple blue square with an "L" for now.

### 2. Update `src/main.py`
*   Import `app` from `nicegui`.
*   Call `app.add_static_files('/static', 'src/static')` (with proper path resolution).
*   Use `ui.add_head_html` to add:
    *   `<link rel="manifest" href="/static/manifest.json">`
    *   `<meta name="apple-mobile-web-app-capable" content="yes">`
    *   `<meta name="apple-mobile-web-app-status-bar-style" content="black">`
    *   `<link rel="apple-touch-icon" href="/static/icon.svg">`
    *   `<meta name="theme-color" content="#1976d2">`

## Implementation Progress
- [x] Create `manifest.json`
- [x] Create `icon.svg`
- [x] Update `main.py` to serve files and add head tags
