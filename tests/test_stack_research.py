"""Safety checks for the foreground research runner. No live agents or Beads writes."""

import json
from pathlib import Path
from typing import Any

import pytest
import stack_research as sr

pytestmark = pytest.mark.layer_tool


def events(path: Path, stop: str = "stop", aborted: bool = False) -> None:
    rows = [
        {"type": "session", "id": "session"},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "stopReason": stop,
                "content": [{"type": "text", "text": "READY\u2028ok"}],
            },
        },
        {"type": "agent_settled", "aborted": aborted},
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    )


def test_final_response_accepts_settled_and_unicode(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    events(path)
    assert sr.final_response(path, "session") == "READY\u2028ok"


@pytest.mark.parametrize("reason", ["error", "aborted", "length", "toolUse"])
def test_zero_exit_is_not_success(tmp_path: Path, reason: str) -> None:
    path = tmp_path / "events.jsonl"
    events(path, stop=reason)
    with pytest.raises(sr.RunError, match="successful"):
        sr.final_response(path, "session")


def test_wrong_session_and_aborted_settlement(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    events(path)
    with pytest.raises(sr.RunError):
        sr.final_response(path, "other")
    events(path, aborted=True)
    with pytest.raises(sr.RunError):
        sr.final_response(path, "session")


def session_file(
    tmp_path: Path, model: str = "gpt-6.1-sol", level: str = "high", tool: str = "read"
) -> None:
    rows = [
        {"type": "model_change", "provider": "openai", "modelId": model},
        {"type": "thinking_level_change", "thinkingLevel": level},
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "name": tool}],
            },
        },
    ]
    (tmp_path / "date_session.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows)
    )


def test_effective_model_and_level(tmp_path: Path) -> None:
    session_file(tmp_path)
    sr.verify_session(tmp_path, "session", sr.OWNER)
    session_file(tmp_path, level="low")
    with pytest.raises(sr.RunError, match="reasoning"):
        sr.verify_session(tmp_path, "session", sr.OWNER)
    session_file(tmp_path, model="gpt-6-luna")
    with pytest.raises(sr.RunError, match="model"):
        sr.verify_session(tmp_path, "session", sr.OWNER)


def test_unexpected_tool_is_rejected(tmp_path: Path) -> None:
    session_file(tmp_path, tool="bash")
    with pytest.raises(sr.RunError, match="Unexpected tool"):
        sr.verify_session(tmp_path, "session", sr.OWNER)


def runner(tmp_path: Path) -> sr.Runner:
    sr.save(tmp_path / "state.json", {"baseline": "a" * 40, "tasks": {}})
    return sr.Runner(tmp_path)


def test_stop_file_and_signal_flag(tmp_path: Path) -> None:
    obj = runner(tmp_path)
    obj.stop = True
    with pytest.raises(sr.Stopped):
        obj.check_stop()
    obj.stop = False
    (tmp_path / "STOP").touch()
    with pytest.raises(sr.Stopped):
        obj.check_stop()


def test_partial_stage_is_not_silently_replayed(tmp_path: Path) -> None:
    obj = runner(tmp_path)
    stage = tmp_path / "partial"
    stage.mkdir()
    (stage / "events.jsonl").write_text("partial")
    with pytest.raises(sr.RunError, match="Partial stage"):
        obj.agent("partial", "hello", tmp_path, sr.OWNER)


def test_cached_stage_requires_guard_and_doctor_receipts(tmp_path: Path) -> None:
    obj = runner(tmp_path)
    stage = tmp_path / "cached"
    stage.mkdir()
    sr.save(stage / "receipt.json", {"model": list(sr.OWNER), "session_id": "abc"})
    with pytest.raises(sr.RunError, match="guard/doctor"):
        obj.agent("cached", "test", tmp_path, sr.OWNER)
    sr.save(stage / "guard-ready.json", {"model": sr.OWNER[0]})
    with pytest.raises(sr.RunError, match="guard/doctor"):
        obj.agent("cached", "test", tmp_path, sr.OWNER)


def test_other_owner_stops_before_workspace_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj = runner(tmp_path)
    monkeypatch.setattr(
        sr, "issue", lambda _: {"status": "in_progress", "assignee": "another"}
    )
    with pytest.raises(sr.RunError, match="another actor"):
        obj.run_task("lr-ngj", ())


def test_unresolved_dependency_stops_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj = runner(tmp_path)

    def issue(bead: str) -> dict[str, Any]:
        if bead == "lr-d80":
            return {
                "status": "open",
                "dependencies": [{"id": "lr-ngj", "dependency_type": "blocks"}],
            }
        return {"status": "open"}

    monkeypatch.setattr(sr, "issue", issue)
    with pytest.raises(sr.RunError, match="prerequisite"):
        obj.run_task("lr-d80", ())


def test_completed_task_is_not_reclaimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj = runner(tmp_path)
    obj.state["tasks"]["lr-ngj"] = {"session_id": "abc", "status": "complete"}
    monkeypatch.setattr(
        sr, "issue", lambda _: {"status": "closed", "assignee": "pi-abc"}
    )
    obj.run_task("lr-ngj", ())


def test_closure_checkpoint_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj = runner(tmp_path)
    obj.state["tasks"]["lr-ngj"] = {"session_id": "abc", "status": "reviewed"}
    monkeypatch.setattr(
        sr, "issue", lambda _: {"status": "closed", "assignee": "pi-abc"}
    )
    obj.run_task("lr-ngj", ())
    assert obj.state["tasks"]["lr-ngj"]["status"] == "complete"


def test_wrong_store_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sr, "bd", lambda _: "/wrong/.beads\n")
    with pytest.raises(sr.RunError, match="Wrong Beads"):
        sr.store_check()


def test_only_six_research_beads() -> None:
    assert [bead for bead, _ in sr.TASKS] == [
        "lr-ngj",
        "lr-48d",
        "lr-d80",
        "lr-9o2",
        "lr-3ns",
        "lr-edl",
    ]
    assert "bash" not in sr.ALLOWED_TOOLS
    assert "codemode" not in sr.ALLOWED_TOOLS
    assert "write" not in sr.ALLOWED_TOOLS


@pytest.mark.parametrize(
    "value",
    [{}, {"summary": "x", "status": "complete", "report": "", "limitations": []}],
)
def test_invalid_report_rejected(value: dict[str, Any]) -> None:
    with pytest.raises(sr.RunError):
        sr.check_report(value)


def test_review_is_separate_gate() -> None:
    value = {
        "summary": "Need evidence",
        "verdict": "revise",
        "findings": ["No sources"],
    }
    assert sr.check_report(value, review=True)["verdict"] == "revise"
    with pytest.raises(sr.RunError):
        sr.check_report({"summary": "pass", "verdict": "pass"}, review=True)


def fake_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[sr.Runner, dict[str, Any], list[str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    obj = runner(output)
    records = {
        bead: {"id": bead, "status": "open", "assignee": ""} for bead, _ in sr.TASKS
    }
    closed: list[str] = []
    monkeypatch.setattr(sr, "REPO", repo)
    monkeypatch.setattr(sr, "store_check", lambda: None)
    monkeypatch.setattr(sr, "issue", lambda bead: dict(records[bead]))

    def jj(args: list[str], cwd: Path = repo) -> str:
        if args[:2] == ["workspace", "add"]:
            (Path(args[-1]) / ".jj").mkdir(parents=True)
        if args[:3] == ["log", "-r", "@-"]:
            return "a" * 40
        return ""

    def bd(args: list[str], actor: str = "", stdin: str | None = None) -> str:
        if args[0] == "update":
            record = records[args[1]]
            if "--claim" in args:
                record.update(status="in_progress", assignee=actor)
            if "--status" in args and args[-1] == "closed":
                assert "--if-assignee" in args and "--if-status" in args
                assert record["assignee"] == actor
                closed.append(args[1])
                record["status"] = "closed"
        return ""

    monkeypatch.setattr(sr, "jj", jj)
    monkeypatch.setattr(sr, "bd", bd)
    return obj, records, closed


def test_whole_queue_and_no_phase_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj, records, closed = fake_queue(tmp_path, monkeypatch)
    seen: list[tuple[str, tuple[str, str]]] = []

    def report(
        key: str,
        prompt: str,
        cwd: Path,
        model: tuple[str, str],
        review: bool = False,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        seen.append((key, model))
        if review:
            return {"verdict": "pass", "summary": "Checked", "findings": []}
        return {
            "status": "complete",
            "summary": "Evidence checked",
            "report": "# Report",
            "limitations": [],
        }

    monkeypatch.setattr(obj, "report", report)
    monkeypatch.setattr(obj, "agent", lambda *a, **kw: "READY")
    obj.run()
    assert closed == [bead for bead, _ in sr.TASKS]
    assert all(record["status"] == "closed" for record in records.values())
    assert sum(key.endswith("-review") for key, _ in seen) == 6
    assert sum("-worker-" in key for key, _ in seen) == 5
    assert obj.state["status"] == "complete"
    for bead, _ in sr.TASKS:
        assert (obj.directory / f"{bead}.md").exists()


def test_failed_review_never_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj, records, closed = fake_queue(tmp_path, monkeypatch)

    def report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("review"):
            return {
                "verdict": "revise",
                "summary": "Missing evidence",
                "findings": ["No source"],
            }
        return {
            "status": "complete",
            "summary": "Draft",
            "report": "# Report",
            "limitations": [],
        }

    monkeypatch.setattr(obj, "report", report)
    with pytest.raises(sr.RunError, match="review did not pass"):
        obj.run_task("lr-ngj", ())
    assert not closed
    assert records["lr-ngj"]["status"] == "in_progress"


def test_private_directory_rejects_public_root(tmp_path: Path) -> None:
    tmp_path.chmod(0o755)
    with pytest.raises(sr.RunError, match="private"):
        sr.private_directory(tmp_path)
    tmp_path.chmod(0o700)
    sr.private_directory(tmp_path)


def test_stop_during_notes_prevents_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj, records, closed = fake_queue(tmp_path, monkeypatch)
    original = sr.bd
    note_writes = 0

    def bd(args: list[str], actor: str = "", stdin: str | None = None) -> str:
        nonlocal note_writes
        answer = original(args, actor, stdin)
        if "--design-file" in args:
            note_writes += 1
            if note_writes == 2:
                obj.stop = True
        return answer

    def report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("review"):
            return {"verdict": "pass", "summary": "Checked", "findings": []}
        return {
            "status": "complete",
            "summary": "Checked",
            "report": "# Report",
            "limitations": [],
        }

    monkeypatch.setattr(sr, "bd", bd)
    monkeypatch.setattr(obj, "report", report)
    with pytest.raises(sr.Stopped):
        obj.run_task("lr-ngj", ())
    assert not closed
    assert records["lr-ngj"]["status"] == "in_progress"


def test_stop_terminates_owned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    obj = runner(tmp_path)
    original = sr.subprocess.Popen
    children = []

    def spawn(*args: Any, **kwargs: Any) -> Any:
        child = original(
            [sr.sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        children.append(child)
        return child

    monkeypatch.setattr(sr.subprocess, "Popen", spawn)
    monkeypatch.setattr(sr.time, "sleep", lambda _: setattr(obj, "stop", True))
    with pytest.raises(sr.Stopped):
        obj.agent("test-stop", "synthetic", tmp_path, sr.OWNER, canary=True)
    assert len(children) == 1
    assert children[0].poll() is not None
    assert not (tmp_path / "test-stop" / "receipt.json").exists()


def test_status_detects_stale_running_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    obj = runner(tmp_path)
    obj.state["status"] = "running"
    obj.checkpoint()
    monkeypatch.setattr(sr, "HOME", tmp_path)
    monkeypatch.setattr(
        sr.sys, "argv", ["runner", "status", "--run-dir", str(tmp_path)]
    )
    assert sr.main() == 0
    status = json.loads(capsys.readouterr().out)
    assert status["runner_live"] is False
    assert status["status"].startswith("interrupted")


def test_source_list_excludes_secrets_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".jj").mkdir()
    (tmp_path / "safe.py").write_text("x = 1")
    (tmp_path / ".env").write_text("synthetic")
    (tmp_path / "list.db").write_text("synthetic")
    (tmp_path / "escape.md").symlink_to("/etc/passwd")
    monkeypatch.setattr(sr, "jj", lambda *args: "safe.py\n.env\nlist.db\nescape.md\n")
    assert sr.source_files(tmp_path, tmp_path) == [str(tmp_path / "safe.py")]
