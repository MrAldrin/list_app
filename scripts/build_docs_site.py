from __future__ import annotations

import html
import json
import posixpath
import shutil
import subprocess
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "zensical.toml"
NOTICE_SOURCE = "docs/preview-exclusions.md"
BACKGROUND_SOURCE = "docs/background"
LOCAL_NETWORK_SOURCE = "docs/local-network-testing.md"
REQUIRED_EXCLUDE_RULES = {
    "**",
    "!/README.md",
    "!/AGENTS.md",
    "!/ARCHITECTURE.md",
    "!/docs/**",
    "/docs/local-network-testing.md",
    "/docs/background/**",
    "!/plans/**",
    "!/frontend/",
    "/frontend/**",
    "!/frontend/README.md",
    "/.venv/**",
    "/.env",
    "/.env.*",
    "/.jj/**",
    "/.codex/**",
    "/local_only/**",
    "**/.venv/**",
    "**/.env",
    "**/.env.*",
    "**/.jj/**",
    "**/.codex/**",
    "**/.pytest_cache/**",
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


def safe_site_root(root: Path, site_dir: object) -> Path:
    root = root.resolve()
    if site_dir != "site":
        raise ValueError("this wrapper only cleans and builds the root site/ directory")

    site_root = root / "site"
    if site_root.is_symlink():
        raise ValueError("refusing to build through a site/ symlink")
    if site_root.exists() and not site_root.is_dir():
        raise ValueError("site/ must be a directory before the build")
    return site_root


def excluded_source_routes(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    routes: set[str] = set()

    local_network_guide = root / LOCAL_NETWORK_SOURCE
    if local_network_guide.is_file() and not local_network_guide.is_symlink():
        routes.add(LOCAL_NETWORK_SOURCE)

    background = root / BACKGROUND_SOURCE
    if background.is_symlink():
        raise ValueError("the excluded background directory must not be a symlink")
    if background.is_dir():
        routes.add(f"{BACKGROUND_SOURCE}/")
        for path in background.rglob("*"):
            if path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                routes.add(f"{relative}/")
            elif path.is_file() and path.suffix.lower() == ".md":
                routes.add(relative)

    return tuple(sorted(routes))


def load_project(root: Path, config_path: Path) -> tuple[Path, tuple[str, ...]]:
    root = root.resolve()
    with config_path.open("rb") as config_file:
        project = tomllib.load(config_file)["project"]

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

    return site_root, excluded_source_routes(root)


def clean_site(root: Path, site_root: Path) -> None:
    root = root.resolve()
    if site_root != root / "site":
        raise ValueError("refusing to clean a path other than the root site/ directory")
    if site_root.is_symlink():
        raise ValueError("refusing to remove a site/ symlink")
    if site_root.exists():
        if not site_root.is_dir():
            raise ValueError("site/ must be a directory before the build")
        shutil.rmtree(site_root)


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


def validate_site(
    site_root: Path,
    excluded_routes: tuple[str, ...],
    redirect_paths: set[Path],
) -> int:
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
    for source in excluded_routes:
        route = page_output(site_root, source).parent.relative_to(site_root).as_posix()
        if any(
            location == route or location.startswith(f"{route}/")
            for location in locations
        ):
            raise ValueError(f"excluded route appears in search index: {source}")

    for path in redirect_paths:
        text = path.read_text(encoding="utf-8")
        if "window.location.hash" in text or "#" in text:
            raise ValueError(f"redirect retains a source fragment: {path}")
    return checked_links


def build_site(root: Path, config_path: Path) -> tuple[int, int]:
    root = root.resolve()
    site_root, excluded_routes = load_project(root, config_path)
    clean_site(root, site_root)

    subprocess.run([sys.executable, "-m", "zensical", "build"], cwd=root, check=True)
    redirect_paths = rewrite_redirects(site_root, excluded_routes)
    checked_links = validate_site(site_root, excluded_routes, redirect_paths)
    return len(redirect_paths), checked_links


def main() -> None:
    redirect_count, checked_links = build_site(ROOT, CONFIG)
    print(
        f"Validated {redirect_count} fragment-free redirects and "
        f"{checked_links} generated local links."
    )


if __name__ == "__main__":
    main()
