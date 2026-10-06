"""Build the Svelte app and serve it on the local network for phone testing.

Usage:
    uv run python scripts/serve_svelte_local.py
    uv run python scripts/serve_svelte_local.py --port 8081 --skip-build

Uses a separate test database (never list.db or production) and prints the
addresses to open on the phone. Guide: docs/local-network-testing.md.
"""

import argparse
import ipaddress
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
TEST_DIR = Path.home() / ".local/share/list_app/svelte-phone-test"
DEFAULT_DB = TEST_DIR / "list.db"
DEFAULT_PORT = 8080
TAILSCALE_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def network_addresses() -> list[str]:
    """This computer's IPv4 addresses that other devices can reach."""
    try:
        output = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    addresses = []
    for word in output.split():
        try:
            address = ipaddress.ip_address(word)
        except ValueError:
            continue
        if address.version == 4 and not address.is_loopback:
            addresses.append(word)
    return addresses


def phone_urls(addresses: list[str], port: int) -> list[str]:
    """One line per address, Tailscale first: the Svelte app URL to open."""

    def is_tailscale(address: str) -> bool:
        return ipaddress.ip_address(address) in TAILSCALE_NETWORK

    lines = []
    for address in sorted(addresses, key=lambda a: not is_tailscale(a)):
        label = "Tailscale" if is_tailscale(address) else "Wi-Fi/LAN"
        lines.append(f"http://{address}:{port}/  ({label})")
    return lines


def serve_https_urls(status: dict, port: int) -> list[str]:
    """Tailscale Serve HTTPS addresses that forward to this port."""
    targets = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    urls = []
    for host_port, web in (status.get("Web") or {}).items():
        proxy = (web.get("Handlers") or {}).get("/", {}).get("Proxy")
        if proxy in targets:
            host = host_port.removesuffix(":443")
            urls.append(f"https://{host}/")
    return urls


def tailscale_serve_status() -> dict:
    """`tailscale serve status --json`, or {} when Tailscale is unavailable."""
    try:
        output = subprocess.run(
            ["tailscale", "serve", "status", "--json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return json.loads(output or "{}")
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def server_env(database: Path, base: dict[str, str]) -> dict[str, str]:
    """The app's environment: test database, no auto-reload."""
    return {
        **base,
        "DB_PATH": str(database),
        "APP_RELOAD": "false",
    }


def prepare_database(env: dict[str, str]) -> None:
    """Create or migrate the test database the same way the app does."""
    code = "import database_setup"
    if subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT / "src", env=env, check=False
    ).returncode:
        sys.exit("Could not set up the test database.")


def room_codes(database: Path) -> list[tuple[str, str]]:
    """(name, code) for each room, to type on the start page."""
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        return db.execute("SELECT name, slug FROM rooms ORDER BY name").fetchall()


def build_frontend() -> None:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm not found. Install Node 24 with fnm (see frontend/README.md).")
    print("Building the Svelte app (npm run build)…", flush=True)
    if subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=False).returncode:
        sys.exit("npm run build failed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help=f"default: {DEFAULT_DB}"
    )
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    database = args.db.expanduser().resolve()
    if database == (ROOT / "list.db").resolve():
        sys.exit("Use a separate test database, not the repository's list.db.")

    if not args.skip_build:
        build_frontend()
    if not (FRONTEND / "build" / "index.html").is_file():
        sys.exit("No Svelte build found. Run without --skip-build.")
    if not (ROOT / ".env").exists():
        print("No .env found. See README.md#new-jj-workspace.", file=sys.stderr)

    database.parent.mkdir(parents=True, exist_ok=True)
    env = server_env(database, dict(os.environ))
    prepare_database(env)
    print(f"\nTest database: {database}")
    print("Rooms (a new test database has Home; its password is APP_PASSWORD):")
    for name, code in room_codes(database):
        print(f"  {name}: room code {code}")
    https_urls = serve_https_urls(tailscale_serve_status(), args.port)
    print("\nOpen on the phone:")
    if https_urls:
        for url in https_urls:
            print(f"  {url}  (HTTPS, like production)")
    else:
        print("  No Tailscale Serve HTTPS found; see docs/local-network-testing.md.")
        for line in phone_urls(network_addresses(), args.port) or [
            f"http://<laptop-ip>:{args.port}/  (find the IP with `hostname -I`)"
        ]:
            print(f"  {line}")
    print(f"On this laptop: http://localhost:{args.port}/")
    print("Stop with Ctrl+C.\n", flush=True)

    main_py = str(ROOT / "src" / "main.py")
    os.execve(
        sys.executable,
        [sys.executable, main_py, "--port", str(args.port)],
        env,
    )


if __name__ == "__main__":
    main()
