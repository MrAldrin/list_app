import base64
import hashlib
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import deploy_backup
import pytest
from deploy_backup import DeployError

IN_WINDOW = datetime(2026, 9, 29, 19, 0, tzinfo=UTC)  # 21:00 in Oslo
OUT_OF_WINDOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)  # 14:00 in Oslo
VOLUME_LIST = json.dumps(
    {
        "environment": "production",
        "project": "list-project",
        "volumes": [{"id": "vol-1", "mountPath": "/data", "deletedAt": None}],
    }
)


def make_db(path: Path) -> Path:
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE rooms (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO rooms (name) VALUES ('Home')")
        db.commit()
    return path


def output_for(path: Path) -> str:
    """What the remote backup prints for this file, with terminal line ends."""
    data = path.read_bytes()
    result = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    lines = [
        "Welcome banner",
        "BACKUP_RESULT " + json.dumps(result),
        "BACKUP_DATA_BEGIN",
        *base64.encodebytes(data).decode().splitlines(),
        "BACKUP_DATA_END",
    ]
    return "\r\n".join(lines) + "\r\n"


class FakeRailwayAndJj:
    """Records commands and answers them like Railway and jj would."""

    def __init__(self, tmp_path: Path, shipping: str = "abc items - fix\n"):
        self.calls: list[list[str]] = []
        self.source = make_db(tmp_path / "production.db")
        self.remote_output = output_for(self.source)
        self.shipping = shipping
        self.fail_on: str | None = None

    def __call__(self, command: list[str]) -> str:
        self.calls.append(command)
        if self.fail_on and self.fail_on in command:
            raise DeployError(f"{self.fail_on} failed")
        if command[:3] == ["railway", "volume", "list"]:
            return VOLUME_LIST
        if command[:2] == ["railway", "ssh"]:
            return self.remote_output
        if command[:2] == ["jj", "log"]:
            return self.shipping if "main.." in command[4] else ""
        return ""

    def names(self) -> list[str]:
        """Short names for the commands run, in order."""
        short = {"list": "volumes", "curl": "wake", "ssh": "remote-backup"}
        names = []
        for command in self.calls:
            if command[0] == "jj":
                names.append(f"jj {command[1]}")
            else:
                names.append(next(short[w] for w in command if w in short))
        return names


def run_main(tmp_path, fake, argv, answers=(), now=IN_WINDOW):
    replies = iter(answers)
    return deploy_backup.main(
        argv,
        run=fake,
        now=lambda: now,
        ask=lambda prompt: next(replies),
        backup_dir=tmp_path / "backups",
    )


@pytest.mark.parametrize(
    ("utc_hour", "expected"),
    [(17, False), (18, True), (5, True), (6, False)],  # Oslo is UTC+2 in September
)
def test_deploy_window_is_20_to_08_oslo_time(utc_hour, expected):
    now = datetime(2026, 9, 29, utc_hour, 0, tzinfo=UTC)
    assert deploy_backup.in_deploy_window(now) is expected


def test_find_production_volume_returns_data_volume():
    assert deploy_backup.find_production_volume(VOLUME_LIST) == (
        "list-project",
        "vol-1",
    )


@pytest.mark.parametrize(
    "info",
    [
        {"environment": "staging", "volumes": []},
        {"environment": "production", "volumes": []},
        {
            "environment": "production",
            "volumes": [{"id": "old", "mountPath": "/data", "deletedAt": "2026"}],
        },
    ],
)
def test_find_production_volume_rejects_wrong_target(info):
    with pytest.raises(DeployError):
        deploy_backup.find_production_volume(json.dumps(info))


def run_remote_locally(tmp_path, monkeypatch, source: Path) -> str:
    """Run the exact shell command locally instead of over Railway SSH."""
    monkeypatch.setattr(deploy_backup, "SOURCE_DB", str(source))
    temp = tmp_path / "container-tmp"
    temp.mkdir()
    command = deploy_backup.remote_backup_command()
    assert command[:3] == ["railway", "ssh", "--"]
    completed = subprocess.run(
        command[3:],
        capture_output=True,
        text=True,
        env={**os.environ, "TMPDIR": str(temp)},
    )
    assert list(temp.iterdir()) == []  # The temp folder is always removed.
    if completed.returncode != 0:
        raise DeployError(completed.stderr)
    return completed.stdout


def test_remote_command_streams_verified_copy(tmp_path, monkeypatch):
    volume = tmp_path / "volume"
    volume.mkdir()
    source = make_db(volume / "list.db")

    output = run_remote_locally(tmp_path, monkeypatch, source)

    assert list(volume.iterdir()) == [source]  # Nothing new on the volume.
    result, data = deploy_backup.parse_remote_backup(output)
    copy = tmp_path / "copy.db"
    deploy_backup.write_new_file(copy, data)
    deploy_backup.verify_local_backup(copy, result)
    with closing(sqlite3.connect(copy)) as db:
        assert db.execute("SELECT name FROM rooms").fetchall() == [("Home",)]


def test_remote_command_fails_without_source(tmp_path, monkeypatch):
    with pytest.raises(DeployError, match="FileNotFoundError"):
        run_remote_locally(tmp_path, monkeypatch, tmp_path / "missing.db")


def test_parse_remote_backup_accepts_terminal_line_ends(tmp_path):
    source = make_db(tmp_path / "list.db")

    result, data = deploy_backup.parse_remote_backup(output_for(source))

    assert data == source.read_bytes()
    assert result["size"] == len(data)


def test_parse_remote_result_requires_result_line():
    with pytest.raises(DeployError, match="no result"):
        deploy_backup.parse_remote_result("connection closed\n")


def test_parse_remote_result_explains_sleeping_app():
    reply = '{"status":"ready","account":{"id":"x"}}\n'
    with pytest.raises(DeployError, match="did not reach the app's container"):
        deploy_backup.parse_remote_result(reply)


@pytest.mark.parametrize(
    "cut",
    [
        lambda text: text.replace("BACKUP_DATA_END", ""),
        lambda text: text.replace("BACKUP_DATA_BEGIN", ""),
        lambda text: text.replace("BACKUP_DATA_BEGIN\r\n", "BACKUP_DATA_BEGIN\r\n!"),
    ],
)
def test_parse_remote_backup_rejects_incomplete_data(tmp_path, cut):
    output = cut(output_for(make_db(tmp_path / "list.db")))
    with pytest.raises(DeployError, match="missing or incomplete"):
        deploy_backup.parse_remote_backup(output)


def test_write_new_file_refuses_to_overwrite(tmp_path):
    path = tmp_path / "copy.db"
    path.write_bytes(b"older backup")
    with pytest.raises(FileExistsError):
        deploy_backup.write_new_file(path, b"new")
    assert path.read_bytes() == b"older backup"


def test_verify_local_backup_rejects_checksum_mismatch(tmp_path):
    path = make_db(tmp_path / "copy.db")
    expected = {"sha256": "0" * 64, "size": path.stat().st_size}
    with pytest.raises(DeployError, match="Checksum"):
        deploy_backup.verify_local_backup(path, expected)


def test_older_backups_keeps_two_newest_and_ignores_other_files(tmp_path):
    names = [
        "list-manual-20260924T213006Z-6e26b172.db",
        "list-manual-20260928T190328Z-2353c4f8.db",
        "list-deploy-20260929T190000Z-aaaaaaaa.db",
        "list-notes.db",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"")

    assert deploy_backup.older_backups(tmp_path) == [tmp_path / names[0]]


def test_backup_only_wakes_app_then_saves_verified_copy(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)

    assert run_main(tmp_path, fake, ["--backup-only"], now=OUT_OF_WINDOW) == 0

    assert fake.names() == ["volumes", "wake", "remote-backup"]
    assert fake.calls[1][-1] == deploy_backup.APP_URL
    (local,) = (tmp_path / "backups").glob("*.db")
    assert local.read_bytes() == fake.source.read_bytes()
    assert oct(local.stat().st_mode & 0o777) == "0o600"
    assert oct(local.parent.stat().st_mode & 0o777) == "0o700"


def test_push_happens_only_after_backup_and_yes(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=["y"]) == 0

    assert fake.names() == [
        "jj log",
        "jj log",
        "volumes",
        "wake",
        "remote-backup",
        "jj log",
        "jj log",
        "jj bookmark",
        "jj git",
    ]
    assert fake.calls[-2] == ["jj", "bookmark", "set", "main", "-r", "feature"]
    assert fake.calls[-1] == ["jj", "git", "push", "-b", "main"]


def test_no_push_without_yes(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=[""]) == 1

    assert "jj bookmark" not in fake.names()
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1


def test_failed_verification_stops_before_push(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)
    fake.remote_output = fake.remote_output.replace('"sha256": "', '"sha256": "0')

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=["y"]) == 1

    assert "jj bookmark" not in fake.names()
    assert list((tmp_path / "backups").glob("*.db")) == []
    assert len(list((tmp_path / "backups").glob("*.unverified"))) == 1


def test_failed_wake_stops_before_ssh(tmp_path, capsys):
    fake = FakeRailwayAndJj(tmp_path)
    fake.fail_on = "curl"

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=["y"]) == 1

    assert fake.names()[-1] == "wake"
    assert "Could not wake the app" in capsys.readouterr().err


def test_sleeping_app_stops_with_clear_message(tmp_path, capsys):
    fake = FakeRailwayAndJj(tmp_path)
    fake.remote_output = '{"status":"ready","account":{"id":"x"}}\n'

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=["y"]) == 1

    assert fake.names()[-1] == "remote-backup"
    assert "did not reach the app's container" in capsys.readouterr().err
    assert list((tmp_path / "backups").iterdir()) == []


def test_outside_window_push_runs_nothing(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)

    assert run_main(tmp_path, fake, ["--rev", "feature"], now=OUT_OF_WINDOW) == 1

    assert fake.calls == []


def test_nothing_to_ship_stops_before_backup(tmp_path):
    fake = FakeRailwayAndJj(tmp_path, shipping="")

    assert run_main(tmp_path, fake, ["--rev", "main"]) == 1

    assert fake.names() == ["jj log"]


def test_rev_or_backup_only_is_required(tmp_path):
    with pytest.raises(SystemExit):
        run_main(tmp_path, FakeRailwayAndJj(tmp_path), [])


def test_cleanup_deletes_old_backups_only_on_yes(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    old = backups / "list-manual-20260101T000000Z-00000000.db"
    old.write_bytes(b"")
    (backups / "list-manual-20260102T000000Z-00000000.db").write_bytes(b"")
    fake = FakeRailwayAndJj(tmp_path)

    run_main(tmp_path, fake, ["--backup-only"], answers=["n"])
    assert old.exists()

    run_main(tmp_path, fake, ["--backup-only"], answers=["y"])
    assert not old.exists()
    assert len(list(backups.glob("*.db"))) == 2


def test_check_push_ready_with_real_jj(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JJ_USER", "Test")
    monkeypatch.setenv("JJ_EMAIL", "test@example.com")
    run = deploy_backup.run_command
    run(["jj", "git", "init", "--quiet"])
    run(["jj", "describe", "-m", "base"])
    run(["jj", "bookmark", "set", "main", "-r", "@"])
    run(["jj", "new", "-m", "feature"])
    assert "feature" in deploy_backup.check_push_ready(run, "@")

    run(["jj", "new", "main", "-m", "sideways"])
    run(["jj", "bookmark", "set", "main", "-r", "@"])
    with pytest.raises(DeployError, match="not an ancestor"):
        deploy_backup.check_push_ready(run, "description(substring:feature)")
