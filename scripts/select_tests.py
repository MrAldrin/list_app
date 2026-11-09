"""Print conservative test feedback commands. Never execute tests or change gates."""

import argparse
import shlex
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK = "/home/hsa/.local/state/night-loop/list_app/browser.lock"
FULL = [
    "uv run pytest -q",
    "(cd frontend && npm test)",
    f"flock {LOCK} uv run pytest browser_tests -q -n 4",
]
# Explicit starting sets from lr-005.1.2. Unlisted areas stay full, not inferred.
SCRIPTS = {
    "scripts/deploy_backup.py": "tests/test_deploy_backup.py",
    "scripts/seed_test_data.py": "tests/test_seed_test_data.py",
    "scripts/serve_svelte_local.py": "tests/test_serve_svelte_local.py",
    "scripts/build_docs_site.py": "tests/test_docs_site_build.py",
}
REMINDER_SOURCES = {
    f"src/reminders/{name}.py"
    for name in ("due_schedule", "zoned_time", "rules", "policies", "preview")
}
REMINDER_TESTS = [
    f"tests/test_{name}.py"
    for name in (
        "reminders_zoned_time",
        "reminders_rules",
        "reminders_policies",
        "reminders_preview",
        "item_date",
        "item_due_time",
        "due_cycle_start",
        "api_reminders",
        "api_reminders_review",
    )
] + [
    f"browser_tests/test_svelte_{name}.py"
    for name in (
        "item_date",
        "due_center",
        "due_center_phone",
        "policy_editor",
        "timed_due_offline",
    )
]
THEME_SOURCES = {
    f"frontend/src/lib/ui/{name}"
    for name in (
        "theme.ts",
        "theme.svelte.ts",
        "ThemeToggle.svelte",
        "ThemeMenuItem.svelte",
        "AppearanceDialog.svelte",
    )
}
THEME_TESTS = [
    "frontend/src/lib/ui/theme.test.ts",
    "frontend/src/lib/ui/theme.svelte.test.ts",
    "frontend/src/app-colors.test.ts",
] + [
    f"browser_tests/test_svelte_{name}.py"
    for name in (
        "theme",
        "toasts",
        "dialog",
        "bottom_bar",
        "accessibility",
        "tap_targets",
        "phone_fixes",
        "compat",
    )
]


def select(
    entries: list[tuple[str, str]], root: Path
) -> tuple[str, list[str], list[str]]:
    """Return mode, explicit test files and reasons; any uncertainty means full."""
    tests: set[str] = set()
    reasons: list[str] = []
    if not entries:
        return "empty", [], ["No changes; no tests ran."]
    for status, path in entries:
        parts = PurePosixPath(path).parts
        if (
            status != "M"
            or not parts
            or path.startswith("/")
            or ".." in parts
            or "\n" in path
            or "\t" in path
            or not (root / path).is_file()
            or not (root / path).resolve().is_relative_to(root.resolve())
        ):
            return (
                "full",
                [],
                [f"Unsafe, new, deleted or renamed path: {status} {path!r}"],
            )
        if path in SCRIPTS:
            selected = [SCRIPTS[path]]
        elif path in REMINDER_SOURCES:
            selected = REMINDER_TESTS
        elif path in THEME_SOURCES:
            selected = THEME_TESTS
        elif (
            (path.startswith("tests/test_") or path.startswith("browser_tests/test_"))
            and path.endswith(".py")
            and len(parts) == 2
        ) or (path.startswith("frontend/src/") and path.endswith(".test.ts")):
            selected = [path]
        elif path.startswith("docs/background/") and path.endswith(".md"):
            selected = []
        elif path.endswith(".md") and (
            path.startswith("docs/") or path in {"README.md", "ARCHITECTURE.md"}
        ):
            selected = ["tests/test_docs_site_build.py"]
        else:
            return "full", [], [f"Shared/config/helper or unknown area: {path}"]
        if any(not (root / test).is_file() for test in selected):
            return "full", [], [f"Missing mapped test for {path}"]
        tests.update(selected)
        reasons.append(f"{path}: {', '.join(selected) or 'background prose only'}")
    return "selected", sorted(tests), reasons


def commands(mode: str, tests: list[str]) -> list[str]:
    if mode == "full":
        return FULL.copy()
    result: list[str] = []
    for prefix, command in (
        ("tests/", "uv run pytest -q"),
        ("browser_tests/", f"flock {LOCK} uv run pytest -q -n 4"),
        ("frontend/", "npm test --"),
    ):
        paths = [
            p.removeprefix("frontend/") if prefix == "frontend/" else p
            for p in tests
            if p.startswith(prefix)
        ]
        if paths:
            line = command + " " + shlex.join(paths)
            result.append(f"(cd frontend && {line})" if prefix == "frontend/" else line)
    return result


def jj(*args: str) -> str:
    return subprocess.run(
        ["jj", "--no-pager", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_diff(names: str, summary: str) -> list[tuple[str, str]]:
    entries = []
    for line in summary.splitlines():
        if len(line) < 3 or line[1] != " ":
            raise ValueError("Ambiguous jj summary")
        entries.append((line[0], line[2:]))
    if sorted(p for _, p in entries) != sorted(names.splitlines()):
        raise ValueError("Diff names and status disagree")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="integration")
    parser.add_argument("--candidate", default="@")
    args = parser.parse_args()
    print("Optional feedback only. Required checks are unchanged. Run from repo root.")
    try:
        base = jj("log", "-r", args.base, "--no-graph", "-T", 'commit_id ++ "\\n"')
        candidate = jj(
            "log", "-r", args.candidate, "--no-graph", "-T", 'commit_id ++ "\\n"'
        )
        if any(
            len(value) != 40 or any(c not in "0123456789abcdef" for c in value)
            for value in (base, candidate)
        ):
            raise ValueError("Base and candidate must each resolve to one commit")
        print(f"Base: {base}\nCandidate: {candidate}")
        # Mapping and existence checks refer to this working tree, not another tree.
        current = jj("log", "-r", "@", "--no-graph", "-T", "commit_id")
        if candidate != current:
            raise ValueError("Candidate is not the current workspace revision")
        diff_args = ("diff", "--from", base, "--to", candidate)
        entries = parse_diff(jj(*diff_args, "--name-only"), jj(*diff_args, "--summary"))
        mode, tests, reasons = select(entries, ROOT)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        mode, tests, reasons = "full", [], [f"Invalid base/candidate/diff: {error}"]
    print(f"Mode: {mode}")
    for reason in reasons:
        print(f"Reason: {reason}")
    for command in commands(mode, tests):
        print(command)
    print("No tests were executed. Android relevance must be checked separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
