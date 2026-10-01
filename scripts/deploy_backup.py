"""Back up the production database to this machine, then optionally push main.

Usage:
    uv run python scripts/deploy_backup.py --backup-only
    uv run python scripts/deploy_backup.py --rev <revision>

The push only happens after a verified local backup and a typed "y".
Procedure and reasoning: docs/deployment.md#backup-before-deploying.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import shlex
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKUP_DIR = Path.home() / ".local/share/list_app/backups"
VOLUME_MOUNT = "/data"
SOURCE_DB = f"{VOLUME_MOUNT}/list.db"
KEEP_BACKUPS = 2
DEPLOY_TIMEZONE = ZoneInfo("Europe/Oslo")
# A sleeping Railway app starts on the first web request.
APP_URL = "https://listapp-production-d627.up.railway.app/"
RESULT_PREFIX = "BACKUP_RESULT "
DATA_BEGIN = "BACKUP_DATA_BEGIN"
DATA_END = "BACKUP_DATA_END"
TIMESTAMP_PATTERN = re.compile(r"-(\d{8}T\d{6}Z)-")

# Runs on the Railway service. Makes a backup-API copy in a temp folder (not
# the volume), checks it, and prints its size and checksum, then the file as
# base64 text between marker lines. The temp folder is always removed.
REMOTE_BACKUP_CODE = """\
import base64, hashlib, json, os, sqlite3, sys, tempfile
from contextlib import closing
from pathlib import Path

source = Path(os.environ['DB_SOURCE']).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='list-backup-') as folder:
    target = Path(folder) / 'backup.db'
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            integrity = dst.execute('PRAGMA integrity_check').fetchall()
            foreign_keys = dst.execute('PRAGMA foreign_key_check').fetchall()
    if integrity != [('ok',)] or foreign_keys:
        raise SystemExit(f'Check failed: {integrity} {foreign_keys}')
    data = target.read_bytes()
result = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
print('BACKUP_RESULT ' + json.dumps(result))
print('BACKUP_DATA_BEGIN')
sys.stdout.write(base64.encodebytes(data).decode())
print('BACKUP_DATA_END')
"""

Runner = Callable[[list[str]], str]


class DeployError(Exception):
    """A step failed; nothing after it runs."""


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployError(
            f"Command failed: {shlex.join(command)}\n"
            f"{result.stdout}{result.stderr}".rstrip()
        )
    return result.stdout


def in_deploy_window(now: datetime) -> bool:
    hour = now.astimezone(DEPLOY_TIMEZONE).hour
    return hour >= 20 or hour < 8


def backup_name(now: datetime, token: str) -> str:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"list-deploy-{stamp}-{token}.db"


def find_production_volume(volume_list_json: str) -> tuple[str, str]:
    """Return (project, volume id) for the linked production /data volume."""
    info = json.loads(volume_list_json)
    if info.get("environment") != "production":
        raise DeployError(
            f"Linked Railway environment is {info.get('environment')!r}, "
            "not 'production'. Run `railway link` first."
        )
    volumes = [
        volume
        for volume in info.get("volumes", [])
        if volume.get("mountPath") == VOLUME_MOUNT and not volume.get("deletedAt")
    ]
    if len(volumes) != 1:
        raise DeployError(
            f"Expected one volume at {VOLUME_MOUNT}, found {len(volumes)}"
        )
    return info.get("project", "?"), volumes[0]["id"]


def wake_app(run: Runner) -> None:
    print(f"Waking the app: {APP_URL}")
    curl = ["curl", "--fail", "--silent", "--show-error", "--output", "/dev/null"]
    try:
        run([*curl, "--max-time", "90", "--retry", "2", "--retry-all-errors", APP_URL])
    except DeployError as error:
        raise DeployError(f"Could not wake the app at {APP_URL}\n{error}") from None


def remote_backup_command() -> list[str]:
    script = (
        f"DB_SOURCE={shlex.quote(SOURCE_DB)} python - <<'PY'\n{REMOTE_BACKUP_CODE}PY"
    )
    return ["railway", "ssh", "--", "sh", "-c", script]


def parse_remote_result(output: str) -> dict:
    for line in reversed(output.splitlines()):
        if line.startswith(RESULT_PREFIX):
            result = json.loads(line.removeprefix(RESULT_PREFIX))
            if isinstance(result.get("sha256"), str) and isinstance(
                result.get("size"), int
            ):
                return result
    if '"account"' in output:
        # Seen when the app is asleep: Railway's account service answers
        # instead of the container.
        raise DeployError(
            "railway ssh did not reach the app's container (Railway's account "
            "service answered instead). The app may still be starting; wait a "
            f"minute and run the script again.\n{output}"
        )
    raise DeployError(f"Remote backup gave no result:\n{output}")


def parse_remote_backup(output: str) -> tuple[dict, bytes]:
    """Return (size and checksum, file bytes) from the remote backup output."""
    output = output.replace("\r", "")  # A terminal session may add \r.
    result = parse_remote_result(output)
    lines = output.splitlines()
    try:
        begin = lines.index(DATA_BEGIN)
        end = lines.index(DATA_END, begin)
        data = base64.b64decode("".join(lines[begin + 1 : end]), validate=True)
    except (ValueError, binascii.Error):
        raise DeployError("Remote backup data is missing or incomplete") from None
    return result, data


def write_new_file(path: Path, data: bytes) -> None:
    """Write data to a new 0600 file; refuse to overwrite."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(data)


def verify_local_backup(path: Path, expected: dict) -> None:
    data = path.read_bytes()
    if len(data) != expected["size"]:
        raise DeployError(f"Size mismatch: {len(data)} != {expected['size']}")
    if hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise DeployError("Checksum does not match the Railway copy")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != [("ok",)] or foreign_keys:
        raise DeployError(f"Local check failed: {integrity} {foreign_keys}")


def older_backups(backup_dir: Path, keep: int = KEEP_BACKUPS) -> list[Path]:
    """Backups beyond the newest `keep`, by the timestamp in their name."""
    dated = []
    for path in backup_dir.glob("list-*.db"):
        match = TIMESTAMP_PATTERN.search(path.name)
        if match:
            dated.append((match.group(1), path))
    dated.sort(reverse=True)
    return [path for _, path in dated[keep:]]


def prepare_backup_dir(backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_dir.chmod(0o700)


def take_backup(run: Runner, now: datetime, backup_dir: Path) -> Path:
    project, volume = find_production_volume(
        run(["railway", "volume", "list", "--json"])
    )
    print(f"Railway project {project}, environment production, volume {volume}")

    local_path = backup_dir / backup_name(now, secrets.token_hex(4))
    prepare_backup_dir(backup_dir)
    if local_path.exists():
        raise DeployError(f"Refusing to overwrite {local_path}")

    wake_app(run)
    print("Creating the backup over railway ssh (nothing is written to the volume)")
    expected, data = parse_remote_backup(run(remote_backup_command()))
    print(f"Saving to {local_path}")
    write_new_file(local_path, data)
    try:
        verify_local_backup(local_path, expected)
    except DeployError:
        local_path.rename(local_path.with_suffix(".db.unverified"))
        raise
    print(f"Backup verified: {local_path} ({expected['size']} bytes)")
    return local_path


def offer_cleanup(backup_dir: Path, ask: Callable[[str], str]) -> None:
    old = older_backups(backup_dir)
    if not old:
        return
    print(f"Older backups beyond the newest {KEEP_BACKUPS}:")
    for path in old:
        print(f"  {path}")
    if ask("Delete these? [y/N] ").strip().lower() == "y":
        for path in old:
            path.unlink()
        print("Deleted.")
    else:
        print("Kept.")


def check_push_ready(run: Runner, rev: str) -> str:
    """Return the change list that would ship, or raise if pushing is unsafe."""
    template = 'change_id.short() ++ " " ++ description.first_line() ++ "\\n"'
    shipping = run(["jj", "log", "--no-graph", "-r", f"main..({rev})", "-T", template])
    if not shipping.strip():
        raise DeployError(f"Nothing to ship: {rev} adds no changes over main")
    sideways = run(["jj", "log", "--no-graph", "-r", f"main ~ ::({rev})", "-T", '"x"'])
    if sideways.strip():
        raise DeployError(f"main is not an ancestor of {rev}; rebase first")
    return shipping


def main(
    argv: list[str] | None = None,
    run: Runner = run_command,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ask: Callable[[str], str] = input,
    backup_dir: Path = BACKUP_DIR,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backup-only", action="store_true", help="never push")
    mode.add_argument("--rev", help="jj revision to move main to and push")
    args = parser.parse_args(argv)

    try:
        if args.rev:
            if not in_deploy_window(now()):
                raise DeployError("Outside the deploy window (20:00-08:00 Oslo)")
            check_push_ready(run, args.rev)

        take_backup(run, now(), backup_dir)
        offer_cleanup(backup_dir, ask)
        if args.backup_only:
            return 0

        if not in_deploy_window(now()):
            raise DeployError("The deploy window closed during the backup")
        print(f"\nThese changes will go live (main..{args.rev}):")
        print(check_push_ready(run, args.rev))
        if ask(f"Move main to {args.rev} and push? [y/N] ").strip().lower() != "y":
            print("Not pushed. The backup is kept.")
            return 1
        run(["jj", "bookmark", "set", "main", "-r", args.rev])
        print(run(["jj", "git", "push", "-b", "main"]))
        print("Pushed. Railway now deploys main; do the after-deploy checks.")
        return 0
    except DeployError as error:
        print(f"STOPPED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
