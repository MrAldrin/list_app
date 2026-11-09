"""Separate selector unit tests; not part of the product pytest collection."""

import tempfile
import unittest
from pathlib import Path

from select_tests import (
    FULL,
    REMINDER_TESTS,
    SCRIPTS,
    THEME_TESTS,
    commands,
    parse_diff,
    select,
)


class SelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in [
            *SCRIPTS,
            *SCRIPTS.values(),
            *REMINDER_TESTS,
            *THEME_TESTS,
            "src/reminders/rules.py",
            "frontend/src/lib/ui/theme.ts",
            "docs/testing.md",
            "docs/background/note.md",
        ]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def mode(self, *paths: str) -> tuple[str, list[str], list[str]]:
        return select([("M", path) for path in paths], self.root)

    def test_local_script(self) -> None:
        self.assertEqual(
            self.mode("scripts/deploy_backup.py")[:2],
            ("selected", [SCRIPTS["scripts/deploy_backup.py"]]),
        )

    def test_ui_reminder_union(self) -> None:
        mode, tests, _ = self.mode(
            "frontend/src/lib/ui/theme.ts", "src/reminders/rules.py"
        )
        self.assertEqual(mode, "selected")
        self.assertEqual(tests, sorted(set(THEME_TESTS + REMINDER_TESTS)))
        browser = next(c for c in commands(mode, tests) if "flock" in c)
        self.assertNotIn("chromium", browser)
        self.assertIn("-n 4", browser)

    def test_shared_and_unknown(self) -> None:
        for path in [
            "src/database_setup.py",
            "src/api/access.py",
            "frontend/src/lib/data/index.ts",
            "frontend/src/service-worker.ts",
            "tests/conftest.py",
            "tests/api_helpers.py",
            "pyproject.toml",
            "unknown",
        ]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            with self.subTest(path=path):
                self.assertEqual(self.mode(path)[0], "full")
                self.assertEqual(self.mode("scripts/deploy_backup.py", path)[0], "full")

    def test_test_and_prose(self) -> None:
        self.assertEqual(
            self.mode("tests/test_deploy_backup.py")[1], ["tests/test_deploy_backup.py"]
        )
        self.assertEqual(self.mode("docs/background/note.md")[:2], ("selected", []))
        self.assertEqual(
            self.mode("docs/testing.md")[1], ["tests/test_docs_site_build.py"]
        )

    def test_status_and_unsafe(self) -> None:
        for status in ["A", "D", "R", "C", "?"]:
            self.assertEqual(
                select([(status, "scripts/deploy_backup.py")], self.root)[0], "full"
            )
        for path in ["../outside", "/absolute", "missing", "bad\nname"]:
            self.assertEqual(self.mode(path)[0], "full")

    def test_missing_mapping(self) -> None:
        (self.root / REMINDER_TESTS[0]).unlink()
        self.assertEqual(self.mode("src/reminders/rules.py")[0], "full")

    def test_empty(self) -> None:
        self.assertEqual(select([], self.root)[0], "empty")
        self.assertEqual(commands("empty", []), [])

    def test_diff(self) -> None:
        self.assertEqual(parse_diff("a", "M a"), [("M", "a")])
        for names, summary in [("a", "M b"), ("a", "broken"), ("a", "")]:
            with self.assertRaises(ValueError):
                parse_diff(names, summary)
        self.assertEqual(commands("full", []), FULL)


if __name__ == "__main__":
    unittest.main()
