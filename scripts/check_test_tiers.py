"""Explicit tier self-checks; not part of the existing pytest suite counts.

Run: uv run python scripts/check_test_tiers.py
No browser, server, emulator or frontend test execution.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

# Owner-approved BA.13 decision 1: this is a regression contract, not selection
# logic. Execution uses the decorators, so drift on either side must fail.
CORE_FUNCTIONS = frozenset(
    {
        "browser_tests/test_svelte_accessibility.py::test_focus_returns_to_the_opener_after_a_dialog",
        "browser_tests/test_svelte_compat.py::test_new_server_version_blocks_writes_until_reload",
        "browser_tests/test_svelte_due_center.py::test_bell_counts_overdue_and_today_and_groups_the_panel",
        "browser_tests/test_svelte_due_center.py::test_bell_opens_and_closes_from_the_keyboard",
        "browser_tests/test_svelte_due_center.py::test_timed_due_requires_zone_and_shows_server_confirmation",
        "browser_tests/test_svelte_items.py::test_add_restore_check_quantity_edit_and_undo",
        "browser_tests/test_svelte_items.py::test_suggestion_keyboard_tab_and_touch_selection",
        "browser_tests/test_svelte_live.py::test_password_change_revokes_open_pages",
        "browser_tests/test_svelte_live.py::test_two_phones_see_each_others_changes",
        "browser_tests/test_svelte_offline.py::test_offline_edits_survive_a_reload_and_reach_the_server",
        "browser_tests/test_svelte_offline.py::test_offline_logout_clears_room_but_keeps_share_and_marker",
        "browser_tests/test_svelte_offline.py::test_saved_room_and_share_views_edit_offline_except_online_only_actions",
        "browser_tests/test_svelte_offline_conflicts.py::test_password_reset_holds_edits_after_sign_in_and_reload",
        "browser_tests/test_svelte_offline_conflicts.py::test_refused_tick_is_listed_and_save_mine_anyway_applies",
        "browser_tests/test_svelte_offline_conflicts.py::test_sign_out_with_waiting_changes_asks_first",
        "browser_tests/test_svelte_offline_reconnect.py::test_losing_the_network_keeps_the_open_page_editable_then_back",
        "browser_tests/test_svelte_offline_reconnect.py::test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes",
        "browser_tests/test_svelte_offline_reconnect.py::test_reset_share_link_clears_only_that_saved_share",
        "browser_tests/test_svelte_offline_reconnect.py::test_revoked_password_clears_saved_room_on_reconnect",
        "browser_tests/test_svelte_policy_editor.py::test_two_installations_and_share_link_do_not_leak_policy",
        "browser_tests/test_svelte_private_reminders.py::test_enrollment_settings_and_offline_draft",
        "browser_tests/test_svelte_private_reminders.py::test_revoked_grant_needs_explicit_resume",
        "browser_tests/test_svelte_room_switcher.py::test_switching_to_a_room_without_access_asks_for_its_password",
        "browser_tests/test_svelte_rooms.py::test_reload_during_logout_hides_the_room_and_retries",
        "browser_tests/test_svelte_rooms.py::test_start_page_login_and_remembered_room",
        "browser_tests/test_svelte_service_worker.py::test_built_worker_takes_over_and_serves_a_cold_offline_deep_link",
        "browser_tests/test_svelte_service_worker.py::test_real_build_swap_waits_for_a_stored_room_change",
        "browser_tests/test_svelte_share.py::test_visitor_views_and_edits_by_link_and_reset_stops_it",
        "browser_tests/test_svelte_share.py::test_without_room_access_the_share_page_reveals_nothing_about_the_room",
        "browser_tests/test_svelte_share.py::test_writes_sent_after_a_reset_change_nothing",
        "browser_tests/test_svelte_tap_targets.py::test_list_page_tap_areas_are_44px_tall",
    }
)


def check_core_membership() -> None:
    """Check exact explicit markers, including the paused reminder journeys."""
    marked = []
    marker_references = 0
    for path in (ROOT / "browser_tests").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if ast.unparse(decorator) == "pytest.mark.tier_core":
                        marked.append(
                            f"{path.relative_to(ROOT).as_posix()}::{node.name}"
                        )
        # Reject module/class markers and marker calls as well as extra markers.
        marker_references += sum(
            isinstance(node, ast.Attribute)
            and ast.unparse(node) == "pytest.mark.tier_core"
            for node in ast.walk(tree)
        )
    assert marker_references == len(marked) == 31
    assert set(marked) == CORE_FUNCTIONS, set(marked) ^ CORE_FUNCTIONS


def load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Item:
    """Small collection-item stand-in, without importing browser fixtures."""

    def __init__(
        self,
        suite: str,
        name: str,
        engine: str | None = None,
        body: str = "test_example",
    ) -> None:
        self.path = ROOT / suite / name
        self.originalname = body
        self.callspec = SimpleNamespace(
            params={} if engine is None else {"browser": engine}
        )
        self.marks: list[str] = []

    def add_marker(self, marker: object) -> None:
        self.marks.append(getattr(marker, "name"))


def main() -> None:
    check_core_membership()
    runner = load("tier_runner", ROOT / "scripts/run_test_tier.py")
    labels = load("tier_labels", ROOT / "conftest.py")
    full = runner.commands("full", [], False)
    assert len(full) == 3
    assert "tests" in full[0] and full[1] == ["bun", "run", "test"]
    assert runner.commands("frontend", [], True) == [["bun", "run", "test:list"]]
    assert runner.commands("frontend", [], False) == [["bun", "run", "test"]]
    assert "browser_tests" in full[2]
    assert not any("android_tests" in command for command in full)
    assert not any(x in {"-k", "--tier-engine"} for command in full for x in command)
    # Python's '-m pytest' must not be confused with pytest's marker selector.
    assert all(
        command.count("-m") == (1 if "pytest" in command else 0) for command in full
    )
    for tier in [
        "smoke",
        "core",
        "browser",
        "cross-engine",
        "affected-browser",
        "full",
    ]:
        paths = ["browser_tests"] if tier == "affected-browser" else []
        for command in runner.commands(tier, paths, True):
            if "pytest" in command:
                assert "--collect-only" in command
            if "browser_tests" in command:
                assert command[:4] == [
                    "flock",
                    str(runner.MACHINE_BROWSER_LOCK),
                    "flock",
                    str(runner.BROWSER_LOCK),
                ]
        execution = runner.commands(tier, paths, False)
        collection = runner.commands(tier, paths, True)
        for run, collect in zip(execution, collection, strict=True):
            expected = (
                [*run, "--collect-only", "-n", "0"]
                if "pytest" in run
                else ["bun", "run", "test:list"]
            )
            assert collect == expected, (tier, run, collect)
    # Chromium-only runs use more workers than mixed-engine runs.
    affected = runner.commands("affected-browser", ["browser_tests"], False)[0]
    assert affected[affected.index("-n") + 1] == str(runner.CHROMIUM_WORKERS)
    for tier in ["smoke", "core", "browser"]:
        chromium = runner.commands(tier, [], False)[0]
        assert chromium[chromium.index("--tier-engine") + 1] == "chromium"
        assert chromium[chromium.index("-n") + 1] == str(runner.CHROMIUM_WORKERS)
    core = runner.commands("core", [], False)[0]
    assert core[core.index("pytest") + 1 :] == [
        "-q",
        "browser_tests",
        "-n",
        "6",
        "-m",
        "tier_core",
        "--tier-engine",
        "chromium",
    ]
    assert {node.split("::")[1] for node in CORE_FUNCTIONS} >= labels.SMOKE_BODIES
    cross = runner.commands("cross-engine", [], False)[0]
    assert cross[cross.index("--tier-engine") + 1] == "cross-engine"
    for mixed in [cross, runner.commands("full", [], False)[-1]]:
        assert mixed[mixed.index("-n") + 1] == str(runner.MIXED_ENGINE_WORKERS)
    for paths in [
        [],
        ["tests"],
        ["../list_app/browser_tests"],
        ["browser_tests/missing.py"],
    ]:
        try:
            runner.commands("affected-browser", paths, False)
        except ValueError:
            pass
        else:
            raise AssertionError(paths)
    with (
        patch.object(sys, "argv", ["runner", "full"]),
        patch.object(
            runner.subprocess, "run", return_value=SimpleNamespace(returncode=7)
        ) as run,
    ):
        assert runner.main() == 7
        assert run.call_count == 1
    with (
        patch.object(sys, "argv", ["runner", "full"]),
        patch.object(
            runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ) as run,
    ):
        assert runner.main() == 0 and run.call_count == 3
        assert [call.kwargs["cwd"] for call in run.call_args_list] == [
            ROOT,
            ROOT / "frontend",
            ROOT,
        ]

    for collect in [False, True]:
        for code in [0, 7]:
            argv = ["runner", "core", *(["--collect-only"] if collect else [])]
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    runner.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=code),
                ) as run,
            ):
                assert runner.main() == code
                run.assert_called_once_with(
                    runner.commands("core", [], collect)[0], cwd=ROOT, check=False
                )

    removed: list[Item] = []
    config = SimpleNamespace(
        rootpath=ROOT,
        getoption=lambda name: "chromium",
        hook=SimpleNamespace(pytest_deselected=lambda items: removed.extend(items)),
    )
    items = [
        Item("browser_tests", "test_unknown.py", engine)
        for engine in ["chromium", "firefox", "webkit", None, "future-engine"]
    ]
    labels.pytest_collection_modifyitems(config, items)
    assert len(items) == 3 and len(removed) == 2
    assert all("tier_full" in i.marks and "layer_browser" in i.marks for i in items)
    assert any(i.callspec.params == {} for i in items)
    assert any(i.callspec.params == {"browser": "future-engine"} for i in items)
    config.getoption = lambda name: "cross-engine"
    removed.clear()
    items = [
        Item("browser_tests", "test_unknown.py", engine)
        for engine in ["chromium", "firefox", "webkit", None]
    ]
    labels.pytest_collection_modifyitems(config, items)
    assert [i.callspec.params["browser"] for i in items] == ["firefox", "webkit"]
    assert len(removed) == 2
    python_item = [Item("tests", "test_api_basics.py")]
    labels.pytest_collection_modifyitems(config, python_item)
    assert len(python_item) == 1  # The engine option never cuts other suites.
    config.getoption = lambda name: None
    all_engines = [
        Item("browser_tests", "test_unknown.py", engine)
        for engine in ["chromium", "firefox", "webkit", None]
    ]
    labels.pytest_collection_modifyitems(config, all_engines)
    assert len(all_engines) == 4  # No default engine cuts.
    android = [Item("android_tests", "test_android_chrome.py")]
    labels.pytest_collection_modifyitems(config, android)
    assert {"tier_full", "layer_android"} <= set(android[0].marks)
    layers = {
        "test_api_basics.py": "layer_api",
        "test_migrations.py": "layer_database",
        "test_healthz.py": "layer_tool",
        "test_unknown.py": "layer_service",
    }
    items = [Item("tests", name) for name in layers]
    labels.pytest_collection_modifyitems(config, items)
    for item, layer in zip(items, layers.values(), strict=True):
        assert layer in item.marks and "tier_fast" in item.marks
    smokes = [
        Item("browser_tests", "test_smoke.py", body=body)
        for body in labels.SMOKE_BODIES
    ]
    labels.pytest_collection_modifyitems(config, smokes)
    assert len(smokes) == 4 and all("tier_smoke" in item.marks for item in smokes)
    print(
        "PASS: exact core membership, smoke inclusion, commands, locks, "
        "collection parity, invalid paths, failures, engines and labels"
    )


if __name__ == "__main__":
    main()
