"""The phone-testing script uses a test database and prints phone URLs."""

import os
import socket
import sys
from pathlib import Path

import pytest
import serve_svelte_local as script


def test_phone_urls_list_tailscale_first():
    assert script.phone_urls(["192.168.10.5", "100.121.200.49"], 8080) == [
        "http://100.121.200.49:8080/  (Tailscale)",
        "http://192.168.10.5:8080/  (Wi-Fi/LAN)",
    ]


def test_serve_https_urls_match_the_port():
    status = {
        "Web": {
            "laptop.tail.ts.net:443": {
                "Handlers": {"/": {"Proxy": "http://127.0.0.1:8080"}}
            }
        }
    }
    assert script.serve_https_urls(status, 8080) == ["https://laptop.tail.ts.net/"]
    assert script.serve_https_urls(status, 8081) == []
    assert script.serve_https_urls({}, 8080) == []


def test_server_env_uses_test_database_without_reload(tmp_path: Path):
    database = tmp_path / "phone.db"
    env = script.server_env(
        database, {"APP_RELOAD": "true", "DB_PATH": "list.db", "KEEP": "1"}
    )
    assert env["DB_PATH"] == str(database)
    assert env["APP_RELOAD"] == "false"
    assert env["KEEP"] == "1"


def test_default_database_is_outside_the_repository():
    assert not script.DEFAULT_DB.resolve().is_relative_to(script.ROOT)


def test_room_codes_come_from_the_prepared_database(tmp_path: Path):
    database = tmp_path / "phone.db"
    env = script.server_env(database, {**os.environ, "APP_PASSWORD": "secret"})
    script.prepare_database(env)
    [(name, code)] = script.room_codes(database)
    assert name == "Home"
    assert code.startswith("home-")


def test_port_owner_pids_reads_one_pid():
    output = 'LISTEN 0 2048 0.0.0.0:8080 0.0.0.0:* users:(("python3",pid=1234,fd=6))\n'
    assert script.port_owner_pids(output) == [1234]


def test_port_owner_pids_keeps_several_pids_in_order_without_repeats():
    output = (
        'LISTEN 0 1 0.0.0.0:8080 0.0.0.0:* users:(("a",pid=12,fd=3),("b",pid=7,fd=4))\n'
        'LISTEN 0 1 0.0.0.0:8080 0.0.0.0:* users:(("a",pid=12,fd=5))\n'
    )
    assert script.port_owner_pids(output) == [12, 7]


def test_port_owner_pids_is_empty_without_output():
    assert script.port_owner_pids("") == []


def test_port_in_use_message_names_the_owner():
    message = script.port_in_use_message(8080, (1234, "python3 src/main.py"))
    assert message == (
        "Port 8080 is already in use by pid 1234: python3 src/main.py\n"
        "Stop that server first (Ctrl+C in its terminal, or kill 1234), "
        "or use --port for laptop-only testing."
    )


def test_port_in_use_message_without_an_owner():
    message = script.port_in_use_message(8080, None)
    assert message == (
        "Port 8080 is already in use.\n"
        "Stop that server first (Ctrl+C in its terminal), "
        "or use --port for laptop-only testing."
    )


def test_port_is_free_detects_a_listening_socket():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("0.0.0.0", 0))
        server.listen()
        busy_port = server.getsockname()[1]
        assert script.port_is_free(busy_port) is False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("0.0.0.0", 0))
        free_port = probe.getsockname()[1]
    assert script.port_is_free(free_port) is True


def test_main_stops_before_building_when_the_port_is_busy(monkeypatch):
    def fail_build():
        raise AssertionError("the frontend must not build when the port is busy")

    monkeypatch.setattr(script, "port_is_free", lambda port: False)
    monkeypatch.setattr(script, "port_owner", lambda port: (1, "x"))
    monkeypatch.setattr(script, "build_frontend", fail_build)
    monkeypatch.setattr(sys, "argv", ["serve_svelte_local.py", "--port", "8080"])
    with pytest.raises(SystemExit) as exit_info:
        script.main()
    assert "already in use" in str(exit_info.value)
