from __future__ import annotations

import hashlib
import html
import json
import os
import posixpath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Iterator
from urllib.parse import quote, unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "zensical.toml"
NOTICE_SOURCE = "docs/preview-exclusions.md"
BACKGROUND_SOURCE = "docs/background"
LOCAL_NETWORK_SOURCE = "docs/local-network-testing.md"
OWNER_FILE = ".docs-site-owner.json"
SCRATCH_PREFIX = ".docs-site-build-"
REQUIRED_EXCLUDE_RULES = {
    "**",
    "!/README.md",
    "!/AGENTS.md",
    "!/ARCHITECTURE.md",
    "!/docs/*.md",
    "!/docs/**/*.md",
    "/docs/local-network-testing.md",
    "/docs/background/**",
    "!/docs/allium/public-sharing.allium",
    "!/plans/*.md",
    "!/plans/**/*.md",
    "!/frontend/",
    "/frontend/**",
    "!/frontend/README.md",
    "**/README.md",
    "**/AGENTS.md",
    "**/ARCHITECTURE.md",
    "!/docs/allium/README.md",
    "**/.*",
    "**/.*/**",
    "**/local_only/**",
    "**/*.db",
    "**/*-pre-migration.db*",
    "**/*.sqlite*",
}


class PageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "a" and attributes.get("name"):
            self.ids.add(attributes["name"])
        if tag == "a" and attributes.get("href"):
            self.hrefs.append(attributes["href"])


def project_exclude_rules(project: dict[str, object]) -> set[str]:
    configured = project.get("exclude_docs")
    if isinstance(configured, str):
        rules = configured.splitlines()
    elif isinstance(configured, list) and all(
        isinstance(rule, str) for rule in configured
    ):
        rules = configured
    else:
        raise ValueError("project.exclude_docs must be a string or list of patterns")
    return {rule.strip() for rule in rules if rule.strip()}


def output_files(site_root: Path, *, allow_owner: bool = False) -> tuple[Path, ...]:
    if site_root.is_symlink():
        raise ValueError("refusing to follow output symlink: site root")
    if not site_root.exists():
        return ()
    if not site_root.is_dir():
        raise ValueError("site/ must be a directory before the build")

    files: list[Path] = []
    pending = [site_root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(site_root)
                if entry.is_symlink():
                    raise ValueError(f"refusing to follow output symlink: {relative}")
                if any(part.startswith(".") for part in relative.parts) and not (
                    allow_owner and relative.as_posix() == OWNER_FILE
                ):
                    raise ValueError(f"output contains a hidden path: {relative}")
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    files.append(path)
                else:
                    raise ValueError(f"output contains a non-regular file: {relative}")
    return tuple(files)


def ensure_safe_output_tree(site_root: Path, *, allow_owner: bool = False) -> None:
    output_files(site_root, allow_owner=allow_owner)


def safe_output_path(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"refusing to follow output symlink: {current}")
        if current.exists() and current != absolute and not current.is_dir():
            raise ValueError(f"output parent is not a directory: {current}")
    return absolute


def safe_site_root(root: Path, site_dir: object) -> Path:
    root = root.resolve()
    if site_dir != "site":
        raise ValueError("this wrapper only builds the root site/ directory")

    site_root = safe_output_path(root / "site")
    ensure_safe_output_tree(site_root, allow_owner=True)
    return site_root


def source_path(root: Path, relative: str) -> Path | None:
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"refusing to follow source symlink: {relative}")
    if not path.exists():
        return None
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError(f"expected a regular source file: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"source escapes the repository: {relative}") from error
    return path


def scan_source_tree(root: Path, relative: str) -> tuple[set[str], set[str]]:
    source_root = root / relative
    if source_root.is_symlink():
        raise ValueError(f"refusing to follow source symlink: {relative}/")
    if not source_root.exists():
        return set(), set()
    if not source_root.is_dir():
        raise ValueError(f"expected source directory: {relative}/")

    files: set[str] = set()
    directories: set[str] = {f"{relative}/"}
    pending = [source_root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                source_name = path.relative_to(root).as_posix()
                if entry.is_symlink():
                    raise ValueError(
                        f"refusing to follow source symlink: {source_name}"
                    )
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    directories.add(f"{source_name}/")
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    files.add(source_name)
                elif path.suffix == ".md":
                    raise ValueError(f"expected a regular source file: {source_name}")
    return files, directories


def eligible_sources(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    sources: set[str] = set()
    for relative in ("README.md", "AGENTS.md", "ARCHITECTURE.md"):
        if source_path(root, relative) is not None:
            sources.add(relative)

    docs_files, _ = scan_source_tree(root, "docs")
    plans_files, _ = scan_source_tree(root, "plans")
    for relative in docs_files:
        parts = PurePosixPath(relative).parts
        if (
            PurePosixPath(relative).suffix != ".md"
            or any(part.startswith(".") for part in parts)
            or "local_only" in parts
            or relative == LOCAL_NETWORK_SOURCE
            or relative.startswith(f"{BACKGROUND_SOURCE}/")
            or (
                PurePosixPath(relative).name
                in {"README.md", "AGENTS.md", "ARCHITECTURE.md"}
                and relative != "docs/allium/README.md"
            )
        ):
            continue
        sources.add(relative)
    for relative in plans_files:
        parts = PurePosixPath(relative).parts
        if (
            PurePosixPath(relative).suffix == ".md"
            and not any(part.startswith(".") for part in parts)
            and "local_only" not in parts
            and PurePosixPath(relative).name
            not in {"README.md", "AGENTS.md", "ARCHITECTURE.md"}
        ):
            sources.add(relative)

    frontend = root / "frontend"
    if frontend.is_symlink():
        raise ValueError("refusing to follow source symlink: frontend/")
    frontend_readme = source_path(root, "frontend/README.md")
    if frontend_readme is not None:
        sources.add("frontend/README.md")

    allium_example = source_path(root, "docs/allium/public-sharing.allium")
    if allium_example is not None:
        sources.add("docs/allium/public-sharing.allium")

    for relative in sorted(sources):
        if source_path(root, relative) is None:
            raise ValueError(
                f"eligible source disappeared during inventory: {relative}"
            )
    return tuple(sorted(sources))


def excluded_source_routes(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    routes: set[str] = set()
    if source_path(root, LOCAL_NETWORK_SOURCE) is not None:
        routes.add(LOCAL_NETWORK_SOURCE)

    background = root / BACKGROUND_SOURCE
    if background.is_symlink():
        raise ValueError("the excluded background directory must not be a symlink")
    files, directories = scan_source_tree(root, BACKGROUND_SOURCE)
    routes.update(
        route
        for route in directories
        if not any(
            part.startswith(".") or part == "local_only"
            for part in PurePosixPath(route).parts
        )
    )
    routes.update(
        relative
        for relative in files
        if PurePosixPath(relative).suffix.lower() == ".md"
        and not any(
            part.startswith(".") or part == "local_only"
            for part in PurePosixPath(relative).parts
        )
    )
    return tuple(sorted(routes))


def load_project(
    root: Path, config_path: Path
) -> tuple[Path, tuple[str, ...], tuple[str, ...]]:
    root = root.resolve()
    if config_path.resolve() != root / "zensical.toml":
        raise ValueError("the Zensical config must be at the project root")

    with config_path.open("rb") as config_file:
        project = tomllib.load(config_file)["project"]
    if project.get("docs_dir") != ".":
        raise ValueError("this wrapper only builds from the root docs directory")

    site_root = safe_site_root(root, project.get("site_dir"))
    configured_rules = project_exclude_rules(project)
    unrooted_reinclusions = {
        rule
        for rule in configured_rules
        if rule.startswith("!") and not rule.startswith("!/")
    }
    if unrooted_reinclusions:
        raise ValueError(
            "exclude_docs re-inclusions must be rooted at docs_dir: "
            + ", ".join(sorted(unrooted_reinclusions))
        )

    missing_rules = REQUIRED_EXCLUDE_RULES - configured_rules
    if missing_rules:
        raise ValueError(
            "zensical.toml is missing required rooted privacy rules: "
            + ", ".join(sorted(missing_rules))
        )

    sources = eligible_sources(root)
    routes = excluded_source_routes(root)
    return site_root, routes, sources


@contextmanager
def build_scratch(root: Path) -> Iterator[Path]:
    scratch: Path | None = None
    for _ in range(8):
        candidate = root / f"{SCRATCH_PREFIX}{secrets.token_hex(12)}"
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        scratch = candidate
        break
    if scratch is None:
        raise FileExistsError("could not reserve a unique docs build directory")

    identity = scratch.lstat()
    try:
        yield scratch
    finally:
        try:
            current = scratch.lstat()
            if (
                not stat.S_ISDIR(current.st_mode)
                or stat.S_ISLNK(current.st_mode)
                or (current.st_dev, current.st_ino)
                != (identity.st_dev, identity.st_ino)
            ):
                raise RuntimeError(
                    f"refusing to clean changed docs build directory: {scratch}"
                )
            shutil.rmtree(scratch)
        except FileNotFoundError as error:
            raise RuntimeError(
                f"refusing to clean missing docs build directory: {scratch}"
            ) from error


def create_staging_tree(
    root: Path, staging_root: Path, sources: tuple[str, ...]
) -> None:
    if staging_root.is_symlink() or not staging_root.is_dir():
        raise ValueError("docs staging path must be a real directory")
    for relative in sources:
        target = source_path(root, relative)
        if target is None:
            raise ValueError(f"eligible source disappeared during staging: {relative}")
        link = staging_root / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target.resolve(strict=True), link)
    for relative in sources:
        link = staging_root / relative
        if not link.is_symlink() or link.resolve(strict=True) != (
            root / relative
        ).resolve(strict=True):
            raise ValueError(f"invalid staged source link: {relative}")


def owned_output_manifest(site_root: Path) -> dict[str, str] | None:
    ensure_safe_output_tree(site_root, allow_owner=True)
    if not site_root.exists():
        return None
    owner = site_root / OWNER_FILE
    if owner.is_symlink():
        raise ValueError("refusing to follow output owner symlink")
    if not owner.exists():
        raise ValueError("refusing to replace an unowned site/ directory")
    try:
        data = json.loads(owner.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("site output has an invalid ownership record") from error
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("files"), dict)
        or not all(
            isinstance(name, str) and isinstance(digest, str) and len(digest) == 64
            for name, digest in data["files"].items()
        )
    ):
        raise ValueError("site output has an invalid ownership record")
    expected = data["files"]
    actual_files = {
        path.relative_to(site_root).as_posix(): path
        for path in output_files(site_root, allow_owner=True)
        if path != owner
    }
    if set(actual_files) != set(expected):
        raise ValueError("site output contains unowned or missing files")
    for relative, path in actual_files.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected[relative]:
            raise ValueError(
                f"site output was modified outside the builder: {relative}"
            )
    return expected


def add_output_owner(site_root: Path) -> None:
    files = {
        path.relative_to(site_root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in output_files(site_root)
    }
    (site_root / OWNER_FILE).write_text(
        json.dumps({"version": 1, "files": files}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def remove_owned_output(site_root: Path) -> None:
    if owned_output_manifest(site_root) is None:
        raise ValueError(f"refusing to remove unowned output: {site_root}")
    shutil.rmtree(site_root)


def install_output(generated_site: Path, site_root: Path) -> None:
    add_output_owner(generated_site)
    if not site_root.exists():
        os.replace(generated_site, site_root)
        return

    backup_parent: Path | None = None
    for _ in range(8):
        candidate = (
            site_root.parent / f".{site_root.name}-backup-{secrets.token_hex(12)}"
        )
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        backup_parent = candidate
        break
    if backup_parent is None:
        raise FileExistsError("could not reserve a unique docs output backup")

    backup_site = backup_parent / site_root.name
    try:
        os.replace(site_root, backup_site)
        try:
            os.replace(generated_site, site_root)
        except BaseException:
            os.replace(backup_site, site_root)
            raise
        try:
            owned_output_manifest(backup_site)
            shutil.rmtree(backup_site)
            backup_parent.rmdir()
        except Exception as error:
            raise RuntimeError(
                f"new preview installed; previous output preserved at {backup_site}"
            ) from error
    except BaseException:
        if backup_site.exists() and not site_root.exists():
            os.replace(backup_site, site_root)
        if backup_parent.exists() and not any(backup_parent.iterdir()):
            backup_parent.rmdir()
        raise


def page_output(site_root: Path, source: str) -> Path:
    path = PurePosixPath(source)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"site path must stay under docs_dir: {source!r}")

    if source.endswith("/"):
        route = path
    elif path.suffix == ".md":
        route = (
            path.parent if path.stem in {"README", "index"} else path.with_suffix("")
        )
    else:
        raise ValueError(
            f"redirect path must be a Markdown page or directory: {source!r}"
        )

    return site_root.joinpath(*route.parts, "index.html")


def redirect_html(source_page: Path, target_page: Path) -> str:
    relative_target = posixpath.relpath(
        target_page.parent.as_posix(), start=source_page.parent.as_posix()
    )
    target_url = quote(relative_target, safe="/-._~") + "/"
    if "#" in target_url:
        raise ValueError("redirect targets must not carry a section fragment")

    escaped_target = html.escape(target_url, quote=True)
    script_target = json.dumps(target_url)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={escaped_target}">
  <link rel="canonical" href="{escaped_target}">
  <title>Preview exclusions</title>
  <script>window.location.replace({script_target});</script>
</head>
<body>
  <p>This source is not included in the local preview. See the
  <a href="{escaped_target}">preview exclusions notice</a>.</p>
</body>
</html>
"""


def rewrite_redirects(site_root: Path, excluded_routes: tuple[str, ...]) -> set[Path]:
    ensure_safe_output_tree(site_root)
    target_page = page_output(site_root, NOTICE_SOURCE)
    if not target_page.is_file():
        raise FileNotFoundError(f"redirect target {NOTICE_SOURCE!r} was not generated")

    redirect_paths: set[Path] = set()
    for source in excluded_routes:
        source_page = page_output(site_root, source)
        source_page.parent.mkdir(parents=True, exist_ok=True)
        source_page.write_text(
            redirect_html(source_page, target_page), encoding="utf-8"
        )
        redirect_paths.add(source_page.resolve())
    return redirect_paths


def parse_page(path: Path) -> PageLinks:
    parser = PageLinks()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def route_file(site_root: Path, route: str) -> Path:
    relative = PurePosixPath(route.lstrip("/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"link escapes site_dir: {route!r}")
    candidate = site_root.joinpath(*relative.parts)
    if not route or route.endswith("/") or not relative.suffix:
        candidate = candidate / "index.html"
    candidate = candidate.resolve()
    if site_root not in candidate.parents and candidate != site_root:
        raise ValueError(f"link escapes site_dir: {route!r}")
    return candidate


def validate_search_inventory(locations: set[str]) -> None:
    allowed_routes = {"", "AGENTS", "ARCHITECTURE", "frontend"}
    allowed_roots = {"docs", "plans"}
    for location in locations:
        route = location.split("#", maxsplit=1)[0].strip("/")
        path = PurePosixPath(route)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                f"search index route escapes the source inventory: {location}"
            )
        if any(part.startswith(".") for part in path.parts):
            raise ValueError(f"hidden source route appears in search index: {location}")
        if route not in allowed_routes and (
            not path.parts or path.parts[0] not in allowed_roots
        ):
            raise ValueError(
                f"unapproved source route appears in search index: {location}"
            )


def validate_output_file_inventory(site_root: Path) -> None:
    generated_files = {"404.html", "search.json", "sitemap.xml"}
    allowed_source_files = {"docs/allium/public-sharing.allium"}
    for path in site_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(site_root).as_posix()
        if path.suffix == ".html" or relative in generated_files:
            continue
        if relative.split("/", maxsplit=1)[0] == "assets":
            continue
        if relative not in allowed_source_files:
            raise ValueError(f"unapproved file appears in generated site: {relative}")


def validate_site(
    site_root: Path,
    excluded_routes: tuple[str, ...],
    redirect_paths: set[Path],
) -> int:
    ensure_safe_output_tree(site_root)
    validate_output_file_inventory(site_root)
    html_pages = sorted(site_root.rglob("*.html"))
    if not html_pages:
        raise FileNotFoundError("Zensical generated no HTML pages")

    checked_links = 0
    parsed_pages: dict[Path, PageLinks] = {}
    for page in html_pages:
        relative = page.relative_to(site_root)
        if relative.as_posix() == "index.html":
            current_url = "/"
        elif page.name == "index.html":
            current_url = f"/{relative.parent.as_posix().rstrip('/')}/"
        else:
            current_url = f"/{relative.as_posix()}"

        for href in parse_page(page).hrefs:
            destination = urlsplit(urljoin(f"http://local.site{current_url}", href))
            if (
                destination.scheme not in {"http", "https"}
                or destination.netloc != "local.site"
            ):
                continue

            target = route_file(site_root, unquote(destination.path))
            checked_links += 1
            if not target.is_file():
                raise FileNotFoundError(f"broken generated link in {page}: {href}")
            if (
                destination.fragment
                and target.suffix == ".html"
                and target.resolve() not in redirect_paths
            ):
                target = target.resolve()
                if target not in parsed_pages:
                    parsed_pages[target] = parse_page(target)
                if unquote(destination.fragment) not in parsed_pages[target].ids:
                    raise ValueError(f"broken generated anchor in {page}: {href}")

    search_path = site_root / "search.json"
    if not search_path.is_file():
        raise FileNotFoundError("Zensical did not generate search.json")
    search = json.loads(search_path.read_text(encoding="utf-8"))
    locations = {item["location"].strip("/") for item in search["items"]}
    validate_search_inventory(locations)
    location_routes = {
        location.split("#", maxsplit=1)[0].strip("/") for location in locations
    }
    for source in excluded_routes:
        route = page_output(site_root, source).parent.relative_to(site_root).as_posix()
        if any(
            location == route or location.startswith(f"{route}/")
            for location in location_routes
        ):
            raise ValueError(f"excluded route appears in search index: {source}")

    page_routes = set()
    for page in html_pages:
        if page.resolve() in redirect_paths:
            continue
        relative = page.relative_to(site_root)
        if relative.as_posix() == "404.html":
            continue
        if page.name != "index.html":
            raise ValueError(f"unapproved generated page: {relative}")
        route = relative.parent.as_posix()
        page_routes.add("" if route == "." else route)
    if page_routes != location_routes:
        raise ValueError(
            "generated page inventory differs from search index: "
            f"unindexed={sorted(page_routes - location_routes)}, "
            f"missing={sorted(location_routes - page_routes)}"
        )

    for path in redirect_paths:
        text = path.read_text(encoding="utf-8")
        if "window.location.hash" in text or "#" in text:
            raise ValueError(f"redirect retains a source fragment: {path}")
    return checked_links


def staged_config_text(config_path: Path, docs_root: Path, output_root: Path) -> str:
    text = config_path.read_text(encoding="utf-8")
    for name, value in (("docs_dir", docs_root), ("site_dir", output_root)):
        pattern = re.compile(rf'(?m)^(\s*{name}\s*=\s*)".*?"(\s*(?:#.*)?)$')
        text, replacements = pattern.subn(
            lambda match: f"{match.group(1)}{json.dumps(str(value))}{match.group(2)}",
            text,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"could not set temporary Zensical {name}")
    return text


def build_site(
    root: Path, config_path: Path, *, output_path: Path | None = None
) -> tuple[int, int]:
    root = root.resolve()
    configured_site, excluded_routes, sources = load_project(root, config_path)
    site_root = (
        configured_site if output_path is None else safe_output_path(output_path)
    )
    if site_root.parent.stat().st_dev != root.stat().st_dev:
        raise ValueError("site output must be on the project filesystem")
    owned_output_manifest(site_root)

    with build_scratch(root) as scratch:
        docs_root = scratch
        create_staging_tree(root, docs_root, sources)
        generated_site = scratch / "output"
        temporary_config = scratch / "zensical.toml"
        temporary_config.write_text(
            staged_config_text(config_path, Path("."), Path("output")),
            encoding="utf-8",
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "zensical",
                "build",
                "--config-file",
                str(temporary_config),
            ],
            cwd=root,
            check=True,
        )
        redirect_paths = rewrite_redirects(generated_site, excluded_routes)
        checked_links = validate_site(generated_site, excluded_routes, redirect_paths)
        install_output(generated_site, site_root)
    return len(redirect_paths), checked_links


def main() -> None:
    redirect_count, checked_links = build_site(ROOT, CONFIG)
    print(
        f"Validated {redirect_count} fragment-free redirects and "
        f"{checked_links} generated local links."
    )


if __name__ == "__main__":
    main()
