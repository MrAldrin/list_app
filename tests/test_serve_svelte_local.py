"""The phone-testing script uses a test database and prints phone URLs."""

from pathlib import Path

import serve_svelte_local as script


def test_phone_urls_list_tailscale_first():
    assert script.phone_urls(["192.168.10.5", "100.121.200.49"], 8080) == [
        "http://100.121.200.49:8080/app/  (Tailscale)",
        "http://192.168.10.5:8080/app/  (Wi-Fi/LAN)",
    ]


def test_server_env_uses_test_database_without_reload(tmp_path: Path):
    database = tmp_path / "phone.db"
    env = script.server_env(
        database, {"APP_RELOAD": "true", "DB_PATH": "list.db", "KEEP": "1"}
    )
    assert env["DB_PATH"] == str(database)
    assert env["NICEGUI_STORAGE_PATH"] == str(tmp_path / "nicegui")
    assert env["APP_RELOAD"] == "false"
    assert env["KEEP"] == "1"


def test_default_database_is_outside_the_repository():
    assert not script.DEFAULT_DB.resolve().is_relative_to(script.ROOT)
