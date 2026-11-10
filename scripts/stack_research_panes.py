"""Shell-first interactive Pi panes for the sequential research runner."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path


class PaneError(RuntimeError):
    """A pane could not be safely started or closed."""


def action(*args: str) -> str:
    result = subprocess.run(
        ["zellij", "action", *args], text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise PaneError(result.stderr.strip() or f"Zellij action failed: {args[0]}")
    return result.stdout


def panes() -> list[dict]:
    return [
        p
        for p in json.loads(action("list-panes", "--all", "--json"))
        if not p["is_plugin"]
    ]


def check_connection() -> None:
    source = os.environ.get("ZELLIJ_PANE_ID")
    if source is None or not any(str(p["id"]) == source for p in panes()):
        raise PaneError("Start this runner inside a live Zellij terminal pane.")
    if Path(os.environ.get("SHELL", "")).name not in ("fish", "bash"):
        raise PaneError("This launcher supports the installed Fish or Bash shell only.")
    if not shutil.which("pi"):
        raise PaneError("Pi is not on PATH.")


class VisiblePane:
    """One owned tab, one shell and at most one interactive Pi process."""

    def __init__(
        self, cwd: Path, folder: Path, name: str, check_stop: Callable[[], None]
    ) -> None:
        self.cwd = cwd.resolve()
        self.folder = folder
        self.name = name[:25]
        self.check_stop = check_stop
        self.tab_id: int | None = None
        self.pane_id: int | None = None

    def record(self, closed: bool = False) -> None:
        (self.folder / "pane.json").write_text(
            json.dumps(
                {
                    "tab_id": self.tab_id,
                    "pane_id": self.pane_id,
                    "closed": closed,
                    "zellij_session": os.environ.get("ZELLIJ_SESSION_NAME"),
                }
            )
        )

    def current(self) -> dict | None:
        found = [p for p in panes() if p["id"] == self.pane_id]
        if not found:
            return None
        if found[0]["tab_id"] != self.tab_id:
            raise PaneError(
                "Pane ownership changed; refusing to send input or close it."
            )
        return found[0]

    def screen(self) -> str:
        return action("dump-screen", "--pane-id", f"terminal_{self.pane_id}")

    def send(self, text: str) -> None:
        if not self.current():
            raise PaneError("Owned pane disappeared.")
        action("write-chars", "--pane-id", f"terminal_{self.pane_id}", text)
        action("write", "--pane-id", f"terminal_{self.pane_id}", "13")

    def is_shell(self, pane: dict) -> bool:
        return (
            Path(pane.get("pane_command") or "").name == Path(os.environ["SHELL"]).name
            and Path(pane.get("pane_cwd") or "/").resolve() == self.cwd
            and not pane.get("is_held")
            and not pane.get("exited")
        )

    def open(self, args: list[str], guard: Path) -> None:
        check_connection()
        self.tab_id = int(
            action(
                "new-tab", "--name", self.name, "--cwd", str(self.cwd), "--no-focus"
            ).strip()
        )
        self.record()
        # No initial program: the user's normal shell starts first.
        deadline = time.monotonic() + 120
        while self.pane_id is None:
            self.check_stop()
            members = [p for p in panes() if p["tab_id"] == self.tab_id]
            if len(members) > 1:
                raise PaneError(
                    "New tab has multiple terminals; refusing to guess a target."
                )
            if members:
                self.pane_id = members[0]["id"]
                self.record()
                break
            if time.monotonic() > deadline:
                raise PaneError("New tab did not produce a terminal.")
            time.sleep(0.1)
        while True:
            self.check_stop()
            pane = self.current()
            if (
                pane
                and Path(pane.get("pane_command") or "").name
                == Path(os.environ["SHELL"]).name
                and not pane.get("is_held")
                and self.screen().strip()
            ):
                break
            if time.monotonic() > deadline:
                raise PaneError("Normal shell did not become ready in the owned pane.")
            time.sleep(0.1)
        marker = "STACK_SHELL_READY"
        self.send("cd -- " + shlex.quote(str(self.cwd)))
        self.send(f"printf '%s\\n' {marker}")
        while not self.is_shell(self.current() or {}) or marker not in [
            line.strip() for line in self.screen().splitlines()
        ]:
            self.check_stop()
            if time.monotonic() > deadline:
                raise PaneError("Could not verify the interactive shell prompt.")
            time.sleep(0.1)
        # Fish and Bash both accept shlex-quoted literal arguments to env.
        launch = ["env", f"LISTR_RESEARCH_GUARD={guard}", *args]
        self.send(shlex.join(launch))

    def verify_ready(
        self, receipt: dict, session_id: str, model: tuple[str, str]
    ) -> None:
        pane = self.current()
        if not pane:
            raise PaneError("Agent pane disappeared before readiness.")
        expected = (session_id, str(self.cwd), str(self.pane_id), model[0], model[1])
        actual = (
            receipt.get("session_id"),
            receipt.get("cwd"),
            receipt.get("pane_id"),
            receipt.get("model"),
            receipt.get("thinking"),
        )
        if actual != expected or receipt.get("mode") != "tui":
            raise PaneError(f"Interactive Pi readiness mismatch: {actual!r}")
        if receipt.get("zellij_session") != os.environ.get("ZELLIJ_SESSION_NAME"):
            raise PaneError("Pi started in a different Zellij session.")
        (self.folder / "DISPATCH").touch(mode=0o600)

    def close_empty_tab(self) -> None:
        if self.tab_id is None or any(p["tab_id"] == self.tab_id for p in panes()):
            return
        tabs = json.loads(action("list-tabs", "--all", "--json"))
        if any(
            tab["tab_id"] == self.tab_id and tab.get("name") == self.name
            for tab in tabs
        ):
            action("close-tab", "--tab-id", str(self.tab_id))

    def close(self) -> None:
        if self.pane_id is None and self.tab_id is not None:
            members = [p for p in panes() if p["tab_id"] == self.tab_id]
            if len(members) == 1:
                self.pane_id = members[0]["id"]
                self.record()
            elif members:
                raise PaneError(
                    f"Inspect retained tab {self.tab_id}; terminal ownership is ambiguous."
                )
        if self.pane_id is None or not self.current():
            self.close_empty_tab()
            self.record(closed=True)
            return
        (self.folder / "screen.txt").write_text(self.screen())
        # Let the guard abort/exit Pi back to its normal shell first.
        (self.folder / "SHUTDOWN").touch(mode=0o600)
        deadline = time.monotonic() + 10
        while self.current() and not self.is_shell(self.current() or {}):
            if time.monotonic() > deadline:
                break
            time.sleep(0.1)
        if self.current():
            (self.folder / "shell-returned.txt").write_text(
                str(self.is_shell(self.current() or {}))
            )
            action("close-pane", "--pane-id", f"terminal_{self.pane_id}")
        # Do not launch the next agent until this exact owned pane is gone.
        deadline = time.monotonic() + 10
        while self.current():
            if time.monotonic() > deadline:
                raise PaneError("Owned pane did not close; no next agent will launch.")
            time.sleep(0.1)
        self.close_empty_tab()
        self.record(closed=True)
