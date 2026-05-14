# PWA Navigation & Standalone Mode Investigation

## Problem
When the app is added to the Home Screen (PWA) from a room page (e.g., `/room/my-room`), navigating to a list (e.g., `/list/my-list`) causes the browser's UI (URL bar, share buttons) to reappear. This ruins the "app-like" experience.

## Potential Causes

### 1. Missing `scope` in `manifest.json`
The PWA manifest currently doesn't define a `scope`. By default, some browsers might limit the "standalone" scope to the folder where the manifest is located (which is `/static/`) or the path from which it was installed. 
- If you installed from `/room/my-room`, the browser might think the "app" is only that room.
- Navigating to `/list/...` is seen as "leaving the app," so the browser shows the URL bar for security.

### 2. Manifest Location
The manifest is at `/static/manifest.json`. Serving the manifest from a subfolder can sometimes cause scope issues unless explicitly overridden.

### 3. Navigation between different root paths
The app uses:
- `/room/...`
- `/list/...`
These are sibling paths. If the PWA scope is not set to the root `/`, navigating between them triggers the browser's "out-of-app" behavior.

## Proposed Solutions

### Step 1: Update `manifest.json`
We should explicitly set the `scope` and `start_url`.
- `scope`: `/` (This tells the browser the entire website is the app).
- `start_url`: `/` (The default page when opening the app, though pinning a specific room should still work).

### Step 2: Ensure Manifest is served correctly
Ensure the browser sees the manifest as applying to the whole domain.

## Why it changed recently
Before you added the "room at the root," you might have been working primarily within one URL structure, or you might have installed the app from the root `/`. If you now install "from a room," the browser's guess at the "scope" is more likely to be restricted to that room's path.

## Progress Tracking
- [ ] Research iOS PWA scope behavior for deep-linked installs.
- [ ] Update `manifest.json` with `scope` and `start_url`.
- [ ] Test on mobile device by re-installing the PWA.
