"""Home-screen install manifests (served by src/pwa_routes.py).

A manifest tells the browser how to install the app: its name, icons and the
address the icon opens (`start_url`). Every manifest is a copy of
`static/manifest.json` with only `start_url` changed, so all installs keep one
app identity (`id` and `scope` stay "/"). See docs/home-screen-installation.md.

Manifests are routing hints, never proof of access. They hold no room names,
passwords, tokens or query parameters.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

BASE_MANIFEST_PATH = Path(__file__).resolve().parent / "static" / "manifest.json"
MANIFEST_MEDIA_TYPE = "application/manifest+json"
MANIFEST_CACHE_CONTROL = "no-cache, no-store, must-revalidate"


def manifest_with_start_url(start_url: str) -> dict[str, Any]:
    """Return the base manifest with another launch address."""
    with BASE_MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    manifest["start_url"] = start_url
    return manifest


def room_start_url(base_path: str, slug: str) -> str:
    """The room page address, with the slug encoded as one path part."""
    return f"{base_path}/room/{quote(slug, safe='')}"
