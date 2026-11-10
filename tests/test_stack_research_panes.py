"""Stable-target Zellij launch and cleanup tests; no real panes are opened."""

import json
from pathlib import Path
from typing import Any

import pytest
import stack_research_panes as sp

pytestmark = pytest.mark.layer_tool


def test_shell_first_launch_corrects_cwd_and_closes_only_owned_tab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHELL", "/usr/bin/fish")
    monkeypatch.setenv("ZELLIJ_PANE_ID", "1")
    monkeypatch.setattr(sp.shutil, "which", lambda _: "/bin/pi")
    roster = [{"id": 1, "tab_id": 0, "pane_command": "pi"}]
    calls = []
    marker = False

    def action(*args: str) -> str:
        nonlocal marker
        calls.append(args)
        if args[0] == "new-tab":
            roster.append(
                {
                    "id": 3,
                    "tab_id": 8,
                    "pane_command": "/usr/bin/fish",
                    "pane_cwd": "/home/hsa/projects",
                }
            )
            return "8"
        if args[0] == "write-chars":
            if args[-1].startswith("cd -- "):
                roster[-1]["pane_cwd"] = str(tmp_path)
            if args[-1].startswith("printf "):
                marker = True
        if args[0] == "dump-screen":
            return "prompt\nSTACK_SHELL_READY\n" if marker else "prompt\n"
        if args[0] == "close-pane":
            assert args[-1] == "terminal_3"
            roster.pop()
        if args[0] == "list-tabs":
            return json.dumps(
                [{"tab_id": 0, "name": "user"}, {"tab_id": 8, "name": "list-test"}]
            )
        return ""

    monkeypatch.setattr(sp, "action", action)
    monkeypatch.setattr(sp, "panes", lambda: roster)
    pane = sp.VisiblePane(tmp_path, tmp_path, "list-test", lambda: None)
    pane.open(["pi", "--session-id", "abc"], tmp_path / "guard.json")
    new_tab = next(args for args in calls if args[0] == "new-tab")
    assert "--no-focus" in new_tab
    assert "--" not in new_tab
    assert "--initial-command" not in new_tab
    launch = next(
        args[-1]
        for args in calls
        if args[0] == "write-chars" and args[-1].startswith("env ")
    )
    assert "pi --session-id abc" in launch
    assert "--print" not in launch
    assert "--mode" not in launch
    pane.close()
    assert ("close-tab", "--tab-id", "8") in calls
    assert roster == [{"id": 1, "tab_id": 0, "pane_command": "pi"}]
    assert json.loads((tmp_path / "pane.json").read_text())["closed"] is True
    assert (tmp_path / "shell-returned.txt").read_text() == "True"


def test_readiness_must_match_interactive_pane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZELLIJ_SESSION_NAME", "test")
    pane = sp.VisiblePane(tmp_path, tmp_path, "test", lambda: None)
    pane.tab_id, pane.pane_id = 8, 3
    monkeypatch.setattr(pane, "current", lambda: {"id": 3, "tab_id": 8})
    receipt: dict[str, Any] = {
        "session_id": "abc",
        "cwd": str(tmp_path),
        "pane_id": "3",
        "model": "openai/model",
        "thinking": "high",
        "mode": "json",
        "zellij_session": "test",
    }
    with pytest.raises(sp.PaneError, match="readiness mismatch"):
        pane.verify_ready(receipt, "abc", ("openai/model", "high"))
    assert not (tmp_path / "DISPATCH").exists()
    receipt["mode"] = "tui"
    pane.verify_ready(receipt, "abc", ("openai/model", "high"))
    assert (tmp_path / "DISPATCH").exists()


def test_refuse_input_or_cleanup_after_ownership_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pane = sp.VisiblePane(tmp_path, tmp_path, "test", lambda: None)
    pane.tab_id, pane.pane_id = 8, 3
    monkeypatch.setattr(sp, "panes", lambda: [{"id": 3, "tab_id": 99}])
    with pytest.raises(sp.PaneError, match="ownership"):
        pane.send("stop")
    with pytest.raises(sp.PaneError, match="ownership"):
        pane.close()


def test_do_not_close_tab_with_user_added_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pane = sp.VisiblePane(tmp_path, tmp_path, "test", lambda: None)
    pane.tab_id, pane.pane_id = 8, 3
    monkeypatch.setattr(sp, "panes", lambda: [{"id": 4, "tab_id": 8}])
    monkeypatch.setattr(
        sp, "action", lambda *args: pytest.fail("Must not close user terminal")
    )
    pane.close()


def test_connection_requires_real_source_pane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZELLIJ_PANE_ID", "100")
    monkeypatch.setattr(sp, "panes", lambda: [{"id": 1, "tab_id": 0}])
    with pytest.raises(sp.PaneError, match="live Zellij"):
        sp.check_connection()
