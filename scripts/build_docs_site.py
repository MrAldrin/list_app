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
SITE_ROOT = ROOT / "site"


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


def load_project() -> tuple[Path, dict[str, str]]:
    with CONFIG.open("rb") as config_file:
        project = tomllib.load(config_file)["project"]

    site_root = (ROOT / project["site_dir"]).resolve()
    if site_root != SITE_ROOT.resolve():
        raise ValueError("this wrapper only cleans and builds the site/ directory")

    redirects = project["plugins"]["redirects"]["redirect_maps"]
    if not redirects or any(not isinstance(value, str) for value in redirects.values()):
        raise ValueError("redirect_maps must contain string destinations")
    return site_root, redirects


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


def rewrite_redirects(site_root: Path, redirects: dict[str, str]) -> set[Path]:
    redirect_paths: set[Path] = set()
    for source, target in redirects.items():
        source_page = page_output(site_root, source)
        target_page = page_output(site_root, target)
        if not source_page.is_file():
            raise FileNotFoundError(
                f"Zensical did not generate redirect route {source!r}"
            )
        if not target_page.is_file():
            raise FileNotFoundError(f"redirect target {target!r} was not generated")
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
    site_root: Path, redirects: dict[str, str], redirect_paths: set[Path]
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
    if search_path.is_file():
        search = json.loads(search_path.read_text(encoding="utf-8"))
        locations = {item["location"].strip("/") for item in search["items"]}
        for source in redirects:
            route = source.strip("/")
            if route.endswith(".md"):
                route = route[:-3]
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


def main() -> None:
    site_root, redirects = load_project()
    if site_root.exists():
        shutil.rmtree(site_root)

    subprocess.run([sys.executable, "-m", "zensical", "build"], cwd=ROOT, check=True)
    redirect_paths = rewrite_redirects(site_root, redirects)
    checked_links = validate_site(site_root, redirects, redirect_paths)
    print(
        f"Validated {len(redirect_paths)} fragment-free redirects and "
        f"{checked_links} generated local links."
    )


if __name__ == "__main__":
    main()
