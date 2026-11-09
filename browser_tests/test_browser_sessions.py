"""Normal-browser storage, role isolation and disposable profile cleanup."""

from pathlib import Path

import pytest

from conftest import BrowserSessions


@pytest.mark.parametrize("with_origin", [False, True])
def test_browser_sessions_hydrate_storage_state_without_sharing(
    browser, svelte_server, tmp_path, with_origin
):
    sessions = BrowserSessions(browser, tmp_path)
    try:
        origin = svelte_server.url
        state = {
            "cookies": [{"name": "session", "value": "saved", "url": origin}],
            "origins": (
                [
                    {
                        "origin": origin,
                        "localStorage": [{"name": "key", "value": "saved"}],
                    }
                ]
                if with_origin
                else []
            ),
        }
        member = sessions.new_page("hydrated", storage_state=state)
        member.goto(origin + "/robots.txt")
        assert member.evaluate("document.cookie") == "session=saved"
        assert member.evaluate("localStorage.getItem('key')") == (
            "saved" if with_origin else None
        )
        visitor = sessions.new_page("fresh")
        visitor.goto(origin + "/robots.txt")
        assert visitor.evaluate("document.cookie") == ""
        assert visitor.evaluate("localStorage.getItem('key')") is None
    finally:
        sessions.close()


def test_browser_sessions_preserve_storage_without_sharing_profiles(
    browser, svelte_server, tmp_path
):
    sessions = BrowserSessions(browser, tmp_path)
    profiles = []
    try:
        viewport = {"width": 390, "height": 844}
        member = sessions.new_page("storage-member", viewport=viewport)
        assert member.viewport_size == viewport
        assert member.context.pages == [member]
        # A static document avoids app/worker code: this checks the harness's
        # native storage contract, independently of service-worker installation.
        url = svelte_server.url + "/robots.txt"
        member.goto(url)
        member.evaluate(
            """async () => {
                localStorage.setItem('member-only', 'saved');
                document.cookie = 'member-only=saved; path=/';
                const cache = await caches.open('repro-cache');
                await cache.put('/meta', new Response('payload'));
            }"""
        )
        read_cache = """async () => {
            const cache = await caches.open('repro-cache');
            return (await cache.match('/meta'))?.text();
        }"""
        assert member.evaluate(read_cache) == "payload"
        member.reload()
        assert member.evaluate(read_cache) == "payload"
        assert member.evaluate("localStorage.getItem('member-only')") == "saved"
        assert member.evaluate("document.cookie") == "member-only=saved"

        # The replacement must remain cold until the original document closes.
        replacement = member.context.new_page()
        assert replacement.url == "about:blank"
        member.close()
        assert replacement.context.pages == [replacement]
        replacement.goto(url)
        assert replacement.evaluate(read_cache) == "payload"
        assert replacement.evaluate("localStorage.getItem('member-only')") == "saved"

        visitor = sessions.new_page("storage-visitor", viewport=viewport)
        assert visitor.context.pages == [visitor]
        visitor.goto(url)
        assert visitor.evaluate("localStorage.getItem('member-only')") is None
        assert visitor.evaluate("document.cookie") == ""
        assert visitor.evaluate("caches.keys()") == []
        profiles = [Path(profile.name) for profile in sessions.profiles]
        if browser.browser_type.name == "webkit":
            assert len(set(profiles)) == 2
        else:
            assert profiles == []
        assert all(profile.is_dir() for profile in profiles)
    finally:
        sessions.close()
    assert all(not profile.exists() for profile in profiles)
