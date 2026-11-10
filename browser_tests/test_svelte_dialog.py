"""Dialog close/reopen ordering in the real browser's native event queue."""

import re

import pytest
from playwright.sync_api import expect
from svelte_app import PHONE, sign_in


@pytest.mark.parametrize("close_action", ["cancel", "backdrop"])
@pytest.mark.all_engines
def test_dialog_reopens_before_a_queued_native_close_event(
    svelte_server, open_session, close_action
):
    page = open_session("dialog-reopen", **PHONE)
    sign_in(page, svelte_server)
    bell = page.get_by_role("button", name=re.compile(r"^Due items:"))
    bell.click()
    expect(page.get_by_role("dialog")).to_be_visible()

    page.evaluate(
        """async (action) => {
            const box = document.querySelector('dialog');
            const bell = document.querySelector('button[aria-haspopup="dialog"]');
            if (action === 'cancel') {
                // Escape's cancelable event followed by its native default action.
                if (box.dispatchEvent(new Event('cancel', {cancelable: true}))) {
                    box.close();
                }
            } else {
                const bounds = box.getBoundingClientRect();
                box.dispatchEvent(new MouseEvent('click', {
                    bubbles: true, clientX: bounds.right + 1, clientY: bounds.bottom + 1
                }));
            }
            // Let Svelte apply state changes, then reopen before the native
            // close event's later task. No wall-clock delay or warmed dialog.
            await Promise.resolve();
            bell.click();
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }""",
        close_action,
    )
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(page.get_by_role("heading", name="Due items", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(bell).to_be_focused()
