"""Collection labels only. Default collection and fixtures stay unchanged."""

from pathlib import Path

import pytest

SMOKE_BODIES = frozenset(
    {
        "test_add_restore_check_quantity_edit_and_undo",
        "test_visitor_views_and_edits_by_link_and_reset_stops_it",
        "test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes",
        "test_bell_counts_overdue_and_today_and_groups_the_panel",
    }
)

# File layers from lr-005.1.1, integration 6d4b0dcb. Unknown Python files
# receive the conservative rules/service label, never exclusion from a run.
DATABASE_FILES = frozenset(
    {
        "test_database_crud.py",
        "test_database_setup.py",
        "test_field_rules_migration.py",
        "test_item_name_capitalization_migration.py",
        "test_migrations.py",
        "test_offline_schema_migration.py",
        "test_positive_visibility_migration.py",
        "test_reminders_identity_migration.py",
        "test_tag_settings_migration.py",
        "test_write_atomicity_cross_path.py",
    }
)
TOOL_FILES = frozenset(
    {
        "test_deploy_backup.py",
        "test_docs_site_build.py",
        "test_healthz.py",
        "test_seed_test_data.py",
        "test_serve_svelte_local.py",
        "test_server_shutdown.py",
    }
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--tier-engine",
        choices=["chromium", "cross-engine"],
        help=(
            "chromium: Chromium cases and engine-independent cases. "
            "cross-engine: Firefox and WebKit cases only."
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    selected = []
    deselected = []
    for item in items:
        relative = Path(item.path).relative_to(config.rootpath)
        suite = relative.parts[0]
        labels = ["tier_full"]
        if suite == "tests":
            labels += ["tier_fast", "layer_python"]
            if relative.name.startswith("test_api_"):
                labels.append("layer_api")
            elif relative.name in DATABASE_FILES:
                labels.append("layer_database")
            elif relative.name in TOOL_FILES:
                labels.append("layer_tool")
            else:
                labels.append("layer_service")
        elif suite == "browser_tests":
            labels.append("layer_browser")
            if getattr(item, "originalname", None) in SMOKE_BODIES:
                labels.append("tier_smoke")
        elif suite == "android_tests":
            labels.append("layer_android")
        for label in labels:
            item.add_marker(getattr(pytest.mark, label))
        params = getattr(getattr(item, "callspec", None), "params", {})
        engine = params.get("browser")
        tier_engine = config.getoption("--tier-engine")
        other_engine = engine in {"firefox", "webkit"}
        if suite == "browser_tests" and (
            (tier_engine == "chromium" and other_engine)
            or (tier_engine == "cross-engine" and not other_engine)
        ):
            deselected.append(item)
        else:
            selected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
