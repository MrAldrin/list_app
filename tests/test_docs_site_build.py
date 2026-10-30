from __future__ import annotations

import json
import tomllib
from pathlib import Path

import build_docs_site
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = REPO_ROOT / "zensical.toml"


def test_site_symlink_is_rejected_before_zensical_cleanup(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("safe external sentinel", encoding="utf-8")
    (root / "site").symlink_to(external, target_is_directory=True)
    config = write_test_config(root)

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unsafe site path reached the build")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="symlink"):
        build_docs_site.build_site(root, config)

    assert sentinel.read_text(encoding="utf-8") == "safe external sentinel"
    assert (root / "site").is_symlink()


def test_unrooted_allowlist_rule_is_rejected_before_build(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    config = write_test_config(root, extra_exclude_rule="!README.md")

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unsafe exclusion rules reached the build")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="re-inclusions must be rooted"):
        build_docs_site.build_site(root, config)

    assert not (root / "site").exists()


def test_nested_site_symlink_is_rejected_before_zensical_cleanup(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    preserved = root / "preserved-output"
    preserved.mkdir()
    sentinel = preserved / "keep.txt"
    sentinel.write_text("safe in-project sentinel", encoding="utf-8")
    site = root / "site"
    site.mkdir()
    (site / "nested-link").symlink_to(preserved, target_is_directory=True)
    config = write_test_config(root)

    def unexpected_build(*args, **kwargs):
        raise AssertionError("symlinked output reached Zensical cleanup")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="output symlink"):
        build_docs_site.build_site(root, config)

    assert sentinel.read_text(encoding="utf-8") == "safe in-project sentinel"


@pytest.mark.parametrize(
    "source_path",
    [
        "README.md",
        "AGENTS.md",
        "ARCHITECTURE.md",
        "docs/external-link.md",
        "docs",
        "docs/nested-link",
        "plans/nested-link",
        "frontend/README.md",
        "frontend",
    ],
)
def test_source_symlinks_are_rejected_before_build_or_emission(
    tmp_path, monkeypatch, source_path
):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = "EXTERNAL_SOURCE_SYMLINK_SENTINEL"
    sentinel = outside / "external-link.md"
    sentinel.write_text(f"# {marker}\n", encoding="utf-8")

    link = root / source_path
    if source_path in {"docs", "plans", "frontend"} or source_path.endswith(
        "nested-link"
    ):
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside, target_is_directory=True)
    else:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(sentinel)
    config = write_test_config(root)
    invoked = False

    def unexpected_build(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("source symlink reached Zensical")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="source symlink"):
        build_docs_site.build_site(root, config)

    assert not invoked
    assert not (root / "site").exists()
    assert marker not in "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (root / "site").rglob("*")
        if path.is_file()
    )
    assert sentinel.read_text(encoding="utf-8") == f"# {marker}\n"


def test_non_root_docs_dir_is_rejected_before_build(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    config = write_test_config(root, docs_dir="local_only")

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unsafe source path reached the build")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="root docs directory"):
        build_docs_site.build_site(root, config)

    assert not (root / "site").exists()


def test_unsafe_site_dir_is_rejected_before_external_data_changes(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("safe external sentinel", encoding="utf-8")
    config = write_test_config(root, site_dir="../outside")

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unsafe site path reached the build")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="root site"):
        build_docs_site.build_site(root, config)

    assert sentinel.read_text(encoding="utf-8") == "safe external sentinel"


def test_redirect_html_discards_old_fragments():
    redirect = build_docs_site.redirect_html(
        Path("site/docs/background/deep/index.html"),
        Path("site/docs/preview-exclusions/index.html"),
    )

    assert 'window.location.replace("../../preview-exclusions/")' in redirect
    assert "#" not in redirect


def test_validate_site_rejects_output_symlink_without_reading_its_target(tmp_path):
    site = make_test_site(tmp_path, "temporary page")
    sentinel = tmp_path / "outside.html"
    sentinel.write_text("external output sentinel", encoding="utf-8")
    (site / "index.html").unlink()
    (site / "index.html").symlink_to(sentinel)

    with pytest.raises(ValueError, match="output symlink"):
        build_docs_site.validate_site(site, (), set())

    assert sentinel.read_text(encoding="utf-8") == "external output sentinel"


def test_validate_site_rejects_unapproved_static_output_file(tmp_path):
    site = make_test_site(tmp_path, "")
    private_file = site / "docs" / "private.txt"
    private_file.parent.mkdir(parents=True)
    private_file.write_text("synthetic static sentinel", encoding="utf-8")

    with pytest.raises(ValueError, match="unapproved file appears"):
        build_docs_site.validate_site(site, (), set())


def test_validate_site_rejects_broken_local_link(tmp_path):
    site = make_test_site(tmp_path, '<a href="/missing/">missing</a>')

    with pytest.raises(FileNotFoundError, match="broken generated link"):
        build_docs_site.validate_site(site, (), set())


def test_validate_site_rejects_broken_local_anchor(tmp_path):
    site = make_test_site(tmp_path, '<a href="/target/#missing">missing</a>')
    target = site / "target" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text('<h1 id="present">Target</h1>', encoding="utf-8")

    with pytest.raises(ValueError, match="broken generated anchor"):
        build_docs_site.validate_site(site, (), set())


def test_validate_site_ignores_old_fragment_on_generated_redirect(tmp_path):
    site = make_test_site(
        tmp_path, '<a href="/docs/background/private/#old-anchor">private</a>'
    )
    redirect = site / "docs" / "background" / "private" / "index.html"
    redirect.parent.mkdir(parents=True)
    notice = site / "docs" / "preview-exclusions" / "index.html"
    notice.parent.mkdir(parents=True)
    notice.write_text("<h1>Preview exclusions</h1>", encoding="utf-8")
    redirect.write_text(
        build_docs_site.redirect_html(redirect, notice),
        encoding="utf-8",
    )
    (site / "search.json").write_text(
        json.dumps(
            {"items": [{"location": ""}, {"location": "docs/preview-exclusions"}]}
        ),
        encoding="utf-8",
    )

    assert build_docs_site.validate_site(site, (), {redirect.resolve()}) == 2


@pytest.mark.parametrize(
    ("location", "message"),
    [
        ("docs/.pytest_cache/README", "hidden source route"),
        ("unlisted/README", "unapproved source route"),
    ],
)
def test_validate_site_rejects_routes_outside_emitted_inventory(
    tmp_path, location, message
):
    site = make_test_site(tmp_path, "")
    (site / "search.json").write_text(
        json.dumps({"items": [{"location": location}]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=message):
        build_docs_site.validate_site(site, (), set())


def test_validate_site_rejects_excluded_route_in_search_index(tmp_path):
    site = make_test_site(tmp_path, "")
    search_path = site / "search.json"
    search_path.write_text(
        json.dumps({"items": [{"location": "docs/background/private#secret-section"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="excluded route appears"):
        build_docs_site.validate_site(site, ("docs/background/private.md",), set())


def test_build_uses_rooted_allowlist_and_redirects_new_background_pages(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    config = write_test_config(root)
    sources = {
        "README.md": "PUBLIC_ROOT_README_SENTINEL",
        "AGENTS.md": "PUBLIC_ROOT_AGENTS_SENTINEL",
        "ARCHITECTURE.md": "PUBLIC_ROOT_ARCHITECTURE_SENTINEL",
        "docs/index.md": "PUBLIC_DOCS_INDEX_SENTINEL",
        "docs/guide.md": "PUBLIC_GUIDE_SENTINEL",
        "docs/allium/README.md": "PUBLIC_NESTED_DOCS_README_SENTINEL",
        "docs/allium/public-sharing.allium": "PUBLIC_ALLIUM_EXAMPLE_SENTINEL",
        "docs/private-section/README.md": "PRIVATE_NESTED_DOCS_README_SENTINEL",
        "docs/private-section/AGENTS.md": "PRIVATE_NESTED_DOCS_AGENTS_SENTINEL",
        "docs/private-section/ARCHITECTURE.md": "PRIVATE_NESTED_DOCS_ARCHITECTURE_SENTINEL",
        "plans/private-section/README.md": "PRIVATE_NESTED_PLANS_README_SENTINEL",
        "plans/private-section/AGENTS.md": "PRIVATE_NESTED_PLANS_AGENTS_SENTINEL",
        "docs/preview-exclusions.md": "PUBLIC_EXCLUSIONS_NOTICE_SENTINEL",
        "plans/backlog.md": "PUBLIC_PLAN_SENTINEL",
        "frontend/README.md": "PUBLIC_FRONTEND_README_SENTINEL",
        ".pytest_cache/README.md": "PRIVATE_NESTED_PYTEST_README_SENTINEL",
        ".pytest_cache/AGENTS.md": "PRIVATE_NESTED_PYTEST_AGENTS_SENTINEL",
        ".pytest_cache/private.txt": "PRIVATE_PYTEST_DATA_SENTINEL",
        ".codex/AGENTS.md": "PRIVATE_CODEX_AGENTS_SENTINEL",
        ".venv/README.md": "PRIVATE_VENV_README_SENTINEL",
        "local_only/private.md": "PRIVATE_LOCAL_ONLY_SENTINEL",
        "unlisted/README.md": "PRIVATE_NESTED_README_SENTINEL",
        "unlisted/AGENTS.md": "PRIVATE_NESTED_AGENTS_SENTINEL",
        "unlisted/ARCHITECTURE.md": "PRIVATE_NESTED_ARCHITECTURE_SENTINEL",
        "unlisted/private.txt": "PRIVATE_UNLISTED_DATA_SENTINEL",
        "docs/local-network-testing.md": "PRIVATE_NETWORK_GUIDE_SENTINEL",
        "docs/background/future-review.md": "PRIVATE_FUTURE_REVIEW_SENTINEL",
        "docs/background/future-folder/README.md": "PRIVATE_FUTURE_README_SENTINEL",
        "docs/background/future-folder/AGENTS.md": "PRIVATE_FUTURE_AGENTS_SENTINEL",
        "docs/background/future-folder/private.txt": "PRIVATE_FUTURE_DATA_SENTINEL",
        "unlisted/nested/README.md": "PRIVATE_DEEP_NESTED_README_SENTINEL",
        "unlisted/nested/AGENTS.md": "PRIVATE_DEEP_NESTED_AGENTS_SENTINEL",
        "docs/.private/README.md": "PRIVATE_HIDDEN_DIR_README_SENTINEL",
        "docs/.hidden-file": "PRIVATE_DOTFILE_SENTINEL",
        "docs/.pytest_cache/README.md": "PRIVATE_NESTED_CACHE_README_SENTINEL",
        "docs/.codex/AGENTS.md": "PRIVATE_NESTED_CODEX_AGENTS_SENTINEL",
        "docs/.venv/README.md": "PRIVATE_NESTED_VENV_README_SENTINEL",
        "docs/.env.synthetic": "PRIVATE_NESTED_ENV_SENTINEL",
        "docs/private.txt": "PRIVATE_DOCS_TEXT_SENTINEL",
        "docs/private.yaml": "PRIVATE_DOCS_YAML_SENTINEL",
        "docs/allium/private.allium": "PRIVATE_UNLISTED_ALLIUM_SENTINEL",
        "docs/private.sqlite3": "PRIVATE_SQLITE_SENTINEL",
        "plans/private.txt": "PRIVATE_PLANS_TEXT_SENTINEL",
        "plans/private.json": "PRIVATE_PLANS_JSON_SENTINEL",
        "plans/private.db": "PRIVATE_DATABASE_SENTINEL",
        "plans/local_only/private.md": "PRIVATE_NESTED_LOCAL_ONLY_SENTINEL",
    }
    for relative, marker in sources.items():
        body = f"# {marker}\n"
        if relative == "docs/index.md":
            body += "\n## Landing\n\n[guide](guide.md#guide)\n"
            body += "\n[excluded page](background/future-review.md#private-anchor)\n"
        elif relative == "docs/guide.md":
            body = f"# {marker}\n\n## Guide\n\n[landing](index.md#landing)\n"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    redirect_count, checked_links = build_docs_site.build_site(root, config)

    site = root / "site"
    output_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in site.rglob("*")
        if path.is_file()
    )
    search_text = (site / "search.json").read_text(encoding="utf-8")
    private_markers = [
        marker for marker in sources.values() if marker.startswith("PRIVATE_")
    ]
    assert all(
        marker in output_text
        for marker in sources.values()
        if marker.startswith("PUBLIC_")
    )
    assert all(marker not in output_text for marker in private_markers)
    assert all(marker not in search_text for marker in private_markers)
    assert redirect_count >= 5
    assert checked_links > 0

    future_redirect = site / "docs" / "background" / "future-review" / "index.html"
    assert future_redirect.is_file()
    assert "window.location.hash" not in future_redirect.read_text(encoding="utf-8")
    assert "#" not in future_redirect.read_text(encoding="utf-8")
    assert (
        (root / "docs" / "background" / "future-review.md")
        .read_text(encoding="utf-8")
        .startswith("# PRIVATE_FUTURE_REVIEW_SENTINEL")
    )


def test_staging_tree_includes_untracked_sources_and_omits_exclusions(tmp_path):
    root = tmp_path / "project"
    files = {
        "docs/new-untracked-guide.md": "# New guide",
        "docs/background/private.md": "PRIVATE_BACKGROUND_SENTINEL",
        "docs/background/.private/secret.md": "PRIVATE_HIDDEN_SENTINEL",
        "docs/background/local_only/local.md": "PRIVATE_LOCAL_ONLY_SENTINEL",
        "docs/local-network-testing.md": "PRIVATE_NETWORK_SENTINEL",
        "docs/nested/README.md": "PRIVATE_NESTED_README_SENTINEL",
        "docs/allium/public-sharing.allium": "PUBLIC_ALLIUM_SENTINEL",
        "plans/new-untracked-plan.md": "# New plan",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    sources = build_docs_site.eligible_sources(root)
    assert "docs/new-untracked-guide.md" in sources
    assert "plans/new-untracked-plan.md" in sources
    assert "docs/allium/public-sharing.allium" in sources
    assert not any("background" in source for source in sources)
    assert "docs/local-network-testing.md" not in sources
    assert "docs/nested/README.md" not in sources
    routes = build_docs_site.excluded_source_routes(root)
    assert "docs/background/private.md" in routes
    assert not any(".private" in route or "local_only" in route for route in routes)

    staging = root / "temporary-staging"
    staging.mkdir()
    build_docs_site.create_staging_tree(root, staging, sources)
    assert (staging / "docs/new-untracked-guide.md").is_symlink()
    assert (staging / "docs/new-untracked-guide.md").resolve() == (
        root / "docs/new-untracked-guide.md"
    )
    assert (staging / "plans/new-untracked-plan.md").is_symlink()
    assert (staging / "docs/allium/public-sharing.allium").is_symlink()
    assert not (staging / "docs/background/private.md").exists()
    assert not (staging / "docs/local-network-testing.md").exists()
    assert not (staging / "docs/nested/README.md").exists()
    assert not (staging / "docs").is_symlink()
    staged_links = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_symlink()
    }
    assert staged_links == set(sources)
    assert all(
        path.resolve().is_file() and root in path.resolve().parents
        for path in staging.rglob("*")
        if path.is_symlink()
    )


def test_scratch_collision_is_not_cleaned(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    collision = root / f"{build_docs_site.SCRATCH_PREFIX}collision"
    collision.mkdir()
    sentinel = collision / "user-file.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    monkeypatch.setattr(build_docs_site.secrets, "token_hex", lambda _: "collision")

    with (
        pytest.raises(FileExistsError, match="unique docs build directory"),
        build_docs_site.build_scratch(root),
    ):
        pytest.fail("a colliding scratch directory must not be used")

    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_scratch_cleanup_unlinks_staged_symlinks_without_following_them(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    with build_docs_site.build_scratch(root) as scratch:
        (scratch / "outside-link").symlink_to(external, target_is_directory=True)
        scratch_path = scratch

    assert not scratch_path.exists()
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_unowned_site_output_is_preserved_and_rejected(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    config = write_test_config(root)
    site = root / "site"
    site.mkdir()
    sentinel = site / "user-file.txt"
    sentinel.write_text("preserve me", encoding="utf-8")

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unowned output reached Zensical")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="unowned site"):
        build_docs_site.build_site(root, config)

    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_existing_site_user_artifact_is_preserved_and_rejected(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Home\n", encoding="utf-8")
    (root / "docs/index.md").write_text("# Maintained page\n", encoding="utf-8")
    (root / "docs/preview-exclusions.md").write_text(
        "# Preview exclusions\n", encoding="utf-8"
    )
    config = write_test_config(root)
    build_docs_site.build_site(root, config)

    artifact = root / "site/user-added.txt"
    artifact.write_text("preserve me", encoding="utf-8")

    def unexpected_build(*args, **kwargs):
        raise AssertionError("modified output reached Zensical")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="unowned or missing files"):
        build_docs_site.build_site(root, config)

    assert artifact.read_text(encoding="utf-8") == "preserve me"


def test_existing_site_empty_foreign_directory_is_preserved_and_rejected(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Home\n", encoding="utf-8")
    (root / "docs/index.md").write_text("# Maintained page\n", encoding="utf-8")
    (root / "docs/preview-exclusions.md").write_text(
        "# Preview exclusions\n", encoding="utf-8"
    )
    config = write_test_config(root)
    build_docs_site.build_site(root, config)

    foreign_directory = root / "site/user-added-empty-directory"
    foreign_directory.mkdir()
    original_run = build_docs_site.subprocess.run

    def unexpected_build(*args, **kwargs):
        raise AssertionError("unowned directory reached Zensical")

    monkeypatch.setattr(build_docs_site.subprocess, "run", unexpected_build)
    with pytest.raises(ValueError, match="unowned or missing directories"):
        build_docs_site.build_site(root, config)

    assert foreign_directory.is_dir()
    assert not any(foreign_directory.iterdir())

    foreign_directory.rmdir()
    monkeypatch.setattr(build_docs_site.subprocess, "run", original_run)
    build_docs_site.build_site(root, config)
    assert build_docs_site.owned_output_manifest(root / "site") is not None


def test_failed_validation_preserves_previous_site_and_manual_rebuild_refreshes(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Home\n", encoding="utf-8")
    source = root / "docs/index.md"
    source.write_text("# Initial page\n", encoding="utf-8")
    (root / "docs/preview-exclusions.md").write_text(
        "# Preview exclusions\n", encoding="utf-8"
    )
    config = write_test_config(root)
    build_docs_site.build_site(root, config)
    output = root / "site/docs/index.html"
    previous_output = output.read_text(encoding="utf-8")

    source.write_text("# Updated page\n", encoding="utf-8")
    original_validate = build_docs_site.validate_site

    def failed_validation(*args, **kwargs):
        raise ValueError("synthetic validation failure")

    monkeypatch.setattr(build_docs_site, "validate_site", failed_validation)
    with pytest.raises(ValueError, match="synthetic validation failure"):
        build_docs_site.build_site(root, config)
    assert output.read_text(encoding="utf-8") == previous_output

    monkeypatch.setattr(build_docs_site, "validate_site", original_validate)
    build_docs_site.build_site(root, config)
    assert "Updated page" in output.read_text(encoding="utf-8")


def make_test_site(tmp_path: Path, index_html: str) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(index_html, encoding="utf-8")
    (site / "search.json").write_text('{"items": [{"location": ""}]}', encoding="utf-8")
    return site


def write_test_config(
    root: Path,
    site_dir: str = "site",
    docs_dir: str = ".",
    extra_exclude_rule: str | None = None,
) -> Path:
    project = tomllib.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))["project"]
    exclude_docs = project["exclude_docs"]
    if extra_exclude_rule is not None:
        exclude_docs += f"\n{extra_exclude_rule}"
    config = root / "zensical.toml"
    config.write_text(
        "[project]\n"
        'site_name = "Synthetic privacy test"\n'
        'site_url = "http://localhost/"\n'
        f"docs_dir = {json.dumps(docs_dir)}\n"
        f"site_dir = {json.dumps(site_dir)}\n"
        f"exclude_docs = {json.dumps(exclude_docs)}\n",
        encoding="utf-8",
    )
    return config
