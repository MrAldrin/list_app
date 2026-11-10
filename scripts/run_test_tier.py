"""Run explicit test tiers without changing completion or deployment gates."""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER_LOCK = Path("/home/hsa/.local/state/night-loop/list_app/browser.lock")
# Measured limits for this machine; see docs/browser-testing.md.
MIXED_ENGINE_WORKERS = 4
CHROMIUM_WORKERS = 6
CHROMIUM = ["--tier-engine", "chromium"]


def commands(tier: str, paths: list[str], collect_only: bool) -> list[list[str]]:
    """Build commands; full includes Python, frontend and every browser case."""
    pytest = [sys.executable, "-m", "pytest", "-q"]
    collection = ["--collect-only", "-n", "0"] if collect_only else []

    def python() -> list[str]:
        return [*pytest, "tests", *collection]

    def frontend() -> list[str]:
        # Vitest list is the frontend collection equivalent; do not run tests.
        return (
            ["npm", "exec", "--", "vitest", "list"] if collect_only else ["npm", "test"]
        )

    def browser(selection: list[str], extra: list[str]) -> list[str]:
        chromium_only = "chromium" in extra
        workers = CHROMIUM_WORKERS if chromium_only else MIXED_ENGINE_WORKERS
        return [
            "flock",
            str(BROWSER_LOCK),
            *pytest,
            *selection,
            "-n",
            str(workers),
            *extra,
            *collection,
        ]

    match tier:
        case "python":
            return [python()]
        case "frontend":
            return [frontend()]
        case "fast":
            return [python(), frontend()]
        case "smoke":
            return [browser(["browser_tests"], ["-m", "tier_smoke", *CHROMIUM])]
        case "browser":
            return [browser(["browser_tests"], CHROMIUM)]
        case "cross-engine":
            return [browser(["browser_tests"], ["--tier-engine", "cross-engine"])]
        case "affected-browser":
            if not paths:
                raise ValueError(
                    "affected-browser requires explicit browser paths or node IDs"
                )
            for node in paths:
                path = (ROOT / node.split("::", 1)[0]).resolve()
                if not path.is_relative_to(ROOT / "browser_tests") or not path.exists():
                    raise ValueError(f"Not an existing browser test path: {node}")
            return [browser(paths, CHROMIUM)]
        case "full":
            return [
                python(),
                frontend(),
                browser(["browser_tests"], []),
            ]
        case _:
            raise ValueError(f"Unknown tier: {tier}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tier",
        choices=[
            "python",
            "frontend",
            "fast",
            "smoke",
            "browser",
            "cross-engine",
            "affected-browser",
            "full",
        ],
    )
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    if args.paths and args.tier != "affected-browser":
        parser.error("paths are supported only for affected-browser")
    try:
        runs = commands(args.tier, args.paths, args.collect_only)
    except ValueError as error:
        parser.error(str(error))
    for command in runs:
        print(shlex.join(command), flush=True)
        cwd = ROOT / "frontend" if command[0] == "npm" else ROOT
        result = subprocess.run(command, cwd=cwd, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
