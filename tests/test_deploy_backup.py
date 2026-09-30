import hashlib
import json
import os
import shutil
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


def result_for(path: Path) -> str:
    data = path.read_bytes()
    result = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    return "Welcome banner\nBACKUP_RESULT " + json.dumps(result) + "\n"


class FakeRailwayAndJj:
    """Records commands and answers them like Railway and jj would."""

    def __init__(self, tmp_path: Path, shipping: str = "abc items - fix\n"):
        self.calls: list[list[str]] = []
        self.source = make_db(tmp_path / "production.db")
        self.remote_result = result_for(self.source)
        self.shipping = shipping
        self.fail_on: str | None = None

    def __call__(self, command: list[str]) -> str:
        self.calls.append(command)
        if self.fail_on and self.fail_on in command:
            raise DeployError(f"{self.fail_on} failed")
        if command[:3] == ["railway", "volume", "list"]:
            return VOLUME_LIST
        if command[:2] == ["railway", "ssh"]:
            return self.remote_result
        if "download" in command:
            shutil.copyfile(self.source, command[-1])
            return ""
        if command[:2] == ["jj", "log"]:
            return self.shipping if "main.." in command[4] else ""
        return ""

    def names(self) -> list[str]:
        """Short names for the commands run, in order."""
        short = {"list": "volumes", "ssh": "remote-backup", "download": "download"}
        names = []
        for command in self.calls:
            if command[0] == "jj":
                names.append(f"jj {command[1]}")
            elif "delete" in command:
                names.append("remote-delete")
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


def test_remote_command_makes_verified_copy(tmp_path, monkeypatch):
    # Run the exact shell command locally instead of over Railway SSH.
    source = make_db(tmp_path / "list.db")
    monkeypatch.setattr(deploy_backup, "SOURCE_DB", str(source))
    target = tmp_path / "copy.db"
    command = deploy_backup.remote_backup_command(str(target))
    assert command[:3] == ["railway", "ssh", "--"]

    output = subprocess.run(
        command[3:], capture_output=True, text=True, check=True, env=os.environ
    ).stdout

    result = deploy_backup.parse_remote_result(output)
    assert oct(target.stat().st_mode & 0o777) == "0o600"
    deploy_backup.verify_local_backup(target, result)
    with closing(sqlite3.connect(target)) as db:
        assert db.execute("SELECT name FROM rooms").fetchall() == [("Home",)]


def test_remote_command_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(deploy_backup, "SOURCE_DB", str(make_db(tmp_path / "a.db")))
    target = tmp_path / "copy.db"
    target.write_bytes(b"older backup")
    command = deploy_backup.remote_backup_command(str(target))

    completed = subprocess.run(command[3:], capture_output=True, text=True)

    assert completed.returncode != 0
    assert target.read_bytes() == b"older backup"


def test_parse_remote_result_requires_result_line():
    with pytest.raises(DeployError):
        deploy_backup.parse_remote_result("connection closed\n")


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


def test_backup_only_downloads_verified_copy_and_cleans_volume(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)

    assert run_main(tmp_path, fake, ["--backup-only"], now=OUT_OF_WINDOW) == 0

    assert fake.names() == ["volumes", "remote-backup", "download", "remote-delete"]
    remote_name = fake.calls[-1][-2]
    local = tmp_path / "backups" / remote_name.removeprefix("/")
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
        "remote-backup",
        "download",
        "remote-delete",
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


def test_failed_verification_stops_before_push_and_cleans_volume(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)
    fake.remote_result = fake.remote_result.replace('"sha256": "', '"sha256": "0')

    assert run_main(tmp_path, fake, ["--rev", "feature"], answers=["y"]) == 1

    assert fake.names()[-1] == "remote-delete"
    assert list((tmp_path / "backups").glob("*.db")) == []
    assert len(list((tmp_path / "backups").glob("*.unverified"))) == 1


def test_failed_download_still_cleans_volume(tmp_path):
    fake = FakeRailwayAndJj(tmp_path)
    fake.fail_on = "download"

    assert run_main(tmp_path, fake, ["--backup-only"]) == 1

    assert fake.names()[-1] == "remote-delete"


def test_failed_volume_delete_prints_runnable_command(tmp_path, capsys):
    fake = FakeRailwayAndJj(tmp_path)
    fake.fail_on = "delete"

    assert run_main(tmp_path, fake, ["--backup-only"]) == 0

    name = next((tmp_path / "backups").glob("*.db")).name
    expected = f"  railway volume files --volume vol-1 delete /{name}\n"
    assert expected in capsys.readouterr().out


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
