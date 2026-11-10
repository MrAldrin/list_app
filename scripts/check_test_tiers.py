"""Explicit tier self-checks; not part of the existing pytest suite counts.

Run: uv run python scripts/check_test_tiers.py
No browser, server, emulator or frontend test execution.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


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
    runner = load("tier_runner", ROOT / "scripts/run_test_tier.py")
    labels = load("tier_labels", ROOT / "conftest.py")
    full = runner.commands("full", [], False)
    assert len(full) == 3
    assert "tests" in full[0] and full[1] == ["npm", "test"]
    assert "browser_tests" in full[2]
    assert not any("android_tests" in command for command in full)
    assert not any(x in {"-k", "--tier-engine"} for command in full for x in command)
    # Python's '-m pytest' must not be confused with pytest's marker selector.
    assert all(
        command.count("-m") == (1 if "pytest" in command else 0) for command in full
    )
    for tier in ["smoke", "browser", "cross-engine", "affected-browser", "full"]:
        paths = ["browser_tests"] if tier == "affected-browser" else []
        for command in runner.commands(tier, paths, True):
            if "pytest" in command:
                assert "--collect-only" in command
            if "browser_tests" in command:
                assert command[:2] == ["flock", str(runner.BROWSER_LOCK)]
    # Chromium-only runs use more workers than mixed-engine runs.
    affected = runner.commands("affected-browser", ["browser_tests"], False)[0]
    assert affected[affected.index("-n") + 1] == str(runner.CHROMIUM_WORKERS)
    for tier in ["smoke", "browser"]:
        chromium = runner.commands(tier, [], False)[0]
        assert chromium[chromium.index("--tier-engine") + 1] == "chromium"
        assert chromium[chromium.index("-n") + 1] == str(runner.CHROMIUM_WORKERS)
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
        "PASS: commands, locks, collection, invalid paths, failures, engines and labels"
    )


if __name__ == "__main__":
    main()
