"""Focused regression checks for the frontend error-handling contract.

The project deliberately has no Node.js or browser test dependency, so these
tests inspect the shipped JavaScript source. They guard the specific async
contract that caused a real bug: ``handleApiError`` is async, and every caller
must await it before using its boolean return value.

Interactive browser behaviour is covered by the manual checklist in README and
by the headless-browser smoke run documented in the implementation report.
"""

from __future__ import annotations

import re
from pathlib import Path

JS_DIR = Path(__file__).resolve().parents[1] / "static" / "js"
APP_JS = (JS_DIR / "app.js").read_text(encoding="utf-8")
MODERATION_JS = (JS_DIR / "moderation.js").read_text(encoding="utf-8")


def _lines(source: str):
    return source.splitlines()


def test_handle_api_error_is_async():
    assert re.search(
        r"async function handleApiError\s*\(",
        APP_JS,
    )


def test_every_handle_api_error_call_is_awaited():
    calls = 0
    for number, line in enumerate(_lines(APP_JS), start=1):
        if re.search(r"\bhandleApiError\s*\(", line):
            if "async function handleApiError" in line:
                continue
            if "handleError: handleApiError" in line:
                continue
            assert "await handleApiError(" in line, (
                f"app.js:{number} calls async handleApiError without await: "
                f"{line.strip()}"
            )
            calls += 1
    assert calls == 4


def test_every_handle_error_call_is_awaited():
    calls = 0
    for number, line in enumerate(_lines(MODERATION_JS), start=1):
        if re.search(r"\bhandleError\s*\(", line):
            assert "await handleError(" in line, (
                f"moderation.js:{number} calls async handleError without await: "
                f"{line.strip()}"
            )
            calls += 1
    assert calls == 4


def test_csrf_refresh_is_awaited_before_the_retry_notice():
    start = APP_JS.index('if (error.code === "CSRF_FAILED")')
    end = APP_JS.index("return true;", start)
    branch = APP_JS[start:end]
    assert "await refreshCsrfToken();" in branch
    assert branch.index("await refreshCsrfToken();") < branch.index("notify(")


def test_server_field_errors_are_rendered_beside_the_inputs():
    start = APP_JS.index("} catch (error) {", APP_JS.index("async function submitKudos"))
    end = APP_JS.index("} finally {", start)
    catch_block = APP_JS[start:end]

    assert "await handleApiError(" in catch_block
    assert "error.fields.recipientId" in catch_block
    assert "showFieldError(" in catch_block
    assert "els.recipientError" in catch_block
    assert "error.fields.message" in catch_block
    assert "els.messageError" in catch_block


def test_feed_failure_shows_a_retry_control_that_reloads_the_feed():
    start = APP_JS.index("async function loadFeed")
    end = APP_JS.index("async function loadColleagues", start)
    feed_block = APP_JS[start:end]

    assert "await handleApiError(" in feed_block
    assert "state.feedError = error.message" in feed_block
    assert "els.feedRetry.hidden = !state.feedError" in APP_JS
    assert re.search(
        r'els\.feedRetry\.addEventListener\("click",\s*\(\)\s*=>\s*\{\s*'
        r"loadFeed\(\{ reset: true \}\);",
        APP_JS,
    )


def test_moderation_errors_are_shown_after_the_handler_finishes():
    start = MODERATION_JS.index("async function load(")
    end = MODERATION_JS.index("function openDeleteDialog", start)
    moderation_block = MODERATION_JS[start:end]

    assert moderation_block.count("await handleError(") == 2
    assert "setStatus(" in moderation_block
    assert "errorText(error" in moderation_block
    assert 'return error.message || fallback;' in MODERATION_JS


def test_failed_delete_keeps_the_dialog_open_except_for_approved_flows():
    start = MODERATION_JS.index("async function confirmDelete")
    end = MODERATION_JS.index("list.addEventListener", start)
    delete_block = MODERATION_JS[start:end]

    # Success, already-deleted rows, and session expiry close the dialog.
    assert 'error.code === "KUDOS_NOT_FOUND"' in delete_block
    assert "if (error.status === 401)" in delete_block
    assert delete_block.count("closeDeleteDialog();") == 3

    # Every other failure is shown inside the still-open dialog.
    assert "await handleError(" in delete_block
    assert "showDeleteError(" in delete_block
    assert "dialogConfirm.disabled = false;" in MODERATION_JS
    assert "dialogCancel.disabled = false;" in MODERATION_JS


def test_csrf_failure_was_refreshed_before_delete_dialog_error_is_shown():
    start = MODERATION_JS.index("async function confirmDelete")
    end = MODERATION_JS.index("list.addEventListener", start)
    delete_block = MODERATION_JS[start:end]

    handler_call = delete_block.rindex("await handleError(")
    error_call = delete_block.index("showDeleteError(", handler_call)
    assert handler_call < error_call
