"""Kudos creation, validation, and authorization tests."""

from __future__ import annotations

import json
import sqlite3

import pytest

from db import get_db, transaction
from tests.helpers import (
    auth_headers,
    create_kudos,
    execute,
    fetch_one,
    kudos_row,
    login,
)


def error_code(response) -> str:
    return response.get_json()["error"]["code"]


def test_create_kudos_stores_trimmed_message_and_server_giver(
    client, app, employee_id, colleague_id
):
    token = login(client, employee_id)
    response = create_kudos(
        client,
        token,
        colleague_id,
        "  Thank you for staying late!  ",
    )

    assert response.status_code == 201
    data = response.get_json()["kudos"]
    assert data["message"] == "Thank you for staying late!"
    assert data["giver"] == {"id": employee_id, "name": "Alice Ng"}
    assert data["recipient"] == {"id": colleague_id, "name": "Ben Okafor"}
    assert data["createdAt"]

    row = kudos_row(app, data["id"])
    assert row["giver_id"] == employee_id
    assert row["recipient_id"] == colleague_id
    assert row["message"] == "Thank you for staying late!"
    assert row["is_visible"] == 1


def test_create_ignores_client_supplied_identity_and_metadata(
    client, app, employee_id, colleague_id, admin_id
):
    token = login(client, employee_id)
    response = client.post(
        "/api/kudos",
        json={
            "recipientId": colleague_id,
            "message": "Nice work",
            "giverId": admin_id,
            "id": 999999,
            "role": "admin",
            "isAdmin": True,
            "createdAt": "2000-01-01T00:00:00.000Z",
            "isVisible": False,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.get_json()["kudos"]
    assert data["id"] != 999999
    assert data["giver"]["id"] == employee_id
    assert data["createdAt"] != "2000-01-01T00:00:00.000Z"

    row = kudos_row(app, data["id"])
    assert row["giver_id"] == employee_id
    assert row["is_visible"] == 1


def test_self_kudos_is_rejected(client, app, employee_id):
    token = login(client, employee_id)
    response = create_kudos(client, token, employee_id, "I am great")

    assert response.status_code == 400
    assert error_code(response) == "SELF_KUDOS"
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0


def test_unknown_recipient_is_rejected(client, app, employee_id):
    token = login(client, employee_id)
    response = create_kudos(client, token, 99999, "Hello")

    assert response.status_code == 404
    assert error_code(response) == "RECIPIENT_NOT_FOUND"
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0


def test_inactive_recipient_is_rejected(
    client, app, employee_id, colleague_id
):
    execute(app, "UPDATE users SET is_active = 0 WHERE id = ?", (colleague_id,))
    token = login(client, employee_id)
    response = create_kudos(client, token, colleague_id, "Hello")

    assert response.status_code == 404
    assert error_code(response) == "RECIPIENT_NOT_FOUND"


@pytest.mark.parametrize(
    "message",
    [None, 123, [], {}, ""],
)
def test_invalid_message_types_and_empty_values_are_rejected(
    client, app, employee_id, colleague_id, message
):
    token = login(client, employee_id)
    response = create_kudos(client, token, colleague_id, message)

    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "message" in response.get_json()["error"]["fields"]
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0


def test_whitespace_only_message_is_rejected(client, employee_id, colleague_id):
    token = login(client, employee_id)
    response = create_kudos(client, token, colleague_id, "   \n\t  ")
    assert response.status_code == 400
    assert "message" in response.get_json()["error"]["fields"]


def test_message_length_boundaries(client, employee_id, colleague_id):
    token = login(client, employee_id)

    accepted = create_kudos(client, token, colleague_id, "a" * 500)
    assert accepted.status_code == 201

    rejected = create_kudos(client, token, colleague_id, "a" * 501)
    assert rejected.status_code == 400
    assert "message" in rejected.get_json()["error"]["fields"]


def test_emoji_message_uses_code_point_length(client, employee_id, colleague_id):
    token = login(client, employee_id)
    message = "😀" * 500
    response = create_kudos(client, token, colleague_id, message)
    assert response.status_code == 201
    assert response.get_json()["kudos"]["message"] == message


def test_newline_and_tab_are_allowed(client, employee_id, colleague_id):
    token = login(client, employee_id)
    response = create_kudos(
        client,
        token,
        colleague_id,
        "First line\nSecond line\tand tab",
    )
    assert response.status_code == 201
    assert response.get_json()["kudos"]["message"] == (
        "First line\nSecond line\tand tab"
    )


@pytest.mark.parametrize("message", ["nul\x00byte", "bell\x07", "del\x7f"])
def test_other_control_characters_are_rejected(
    client, employee_id, colleague_id, message
):
    token = login(client, employee_id)
    response = create_kudos(client, token, colleague_id, message)
    assert response.status_code == 400
    assert "message" in response.get_json()["error"]["fields"]


@pytest.mark.parametrize("recipient_id", [None, 0, -1, True, False, "2", 2.0])
def test_invalid_recipient_ids_are_rejected(
    client, employee_id, recipient_id
):
    token = login(client, employee_id)
    response = create_kudos(client, token, recipient_id, "Hello")
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "recipientId" in response.get_json()["error"]["fields"]


def test_both_invalid_fields_are_reported_together(client, employee_id):
    token = login(client, employee_id)
    response = client.post(
        "/api/kudos",
        json={"recipientId": "not-an-int", "message": ""},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert set(response.get_json()["error"]["fields"]) == {
        "recipientId",
        "message",
    }


def test_malformed_json_is_rejected(client, employee_id):
    token = login(client, employee_id)
    response = client.post(
        "/api/kudos",
        data="{not valid json",
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert error_code(response) == "INVALID_JSON"


def test_non_json_content_type_is_rejected(client, employee_id):
    token = login(client, employee_id)
    response = client.post(
        "/api/kudos",
        data=json.dumps({"recipientId": 2, "message": "Hello"}),
        content_type="text/plain",
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert error_code(response) == "INVALID_JSON"


def test_json_array_body_is_rejected(client, employee_id):
    token = login(client, employee_id)
    response = client.post(
        "/api/kudos",
        json=[1, 2, 3],
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert error_code(response) == "INVALID_JSON"


def test_oversized_body_is_rejected(client, app, employee_id, colleague_id):
    token = login(client, employee_id)
    payload = json.dumps(
        {
            "recipientId": colleague_id,
            "message": "x" * 20000,
        }
    )
    response = client.post(
        "/api/kudos",
        data=payload,
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert response.status_code == 413
    assert error_code(response) == "PAYLOAD_TOO_LARGE"
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0


def test_xss_payload_is_stored_as_literal_text(
    client, app, employee_id, colleague_id
):
    token = login(client, employee_id)
    payload = "<script>alert(1)</script>"
    response = create_kudos(client, token, colleague_id, payload)
    assert response.status_code == 201
    assert response.get_json()["kudos"]["message"] == payload

    row = kudos_row(app, response.get_json()["kudos"]["id"])
    assert row["message"] == payload


def test_two_submissions_create_two_rows(
    client, app, employee_id, colleague_id
):
    token = login(client, employee_id)
    first = create_kudos(client, token, colleague_id, "First")
    second = create_kudos(client, token, colleague_id, "Second")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["kudos"]["id"] != second.get_json()["kudos"]["id"]

    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 2


def test_failed_transaction_rolls_back_earlier_inserts(
    app, employee_id, colleague_id
):
    with app.app_context():
        connection = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            with transaction() as tx:
                tx.execute(
                    "INSERT INTO kudos (giver_id, recipient_id, message) "
                    "VALUES (?, ?, ?)",
                    (employee_id, colleague_id, "Valid first insert"),
                )
                # The CHECK constraint rejects a self-kudos, forcing rollback.
                tx.execute(
                    "INSERT INTO kudos (giver_id, recipient_id, message) "
                    "VALUES (?, ?, ?)",
                    (employee_id, employee_id, "Invalid second insert"),
                )

        count = connection.execute(
            "SELECT COUNT(*) AS count FROM kudos"
        ).fetchone()["count"]
        assert count == 0


def test_create_requires_csrf(client, app, employee_id, colleague_id):
    login(client, employee_id)

    missing = client.post(
        "/api/kudos",
        json={"recipientId": colleague_id, "message": "Hello"},
    )
    assert missing.status_code == 403
    assert error_code(missing) == "CSRF_FAILED"

    wrong = client.post(
        "/api/kudos",
        json={"recipientId": colleague_id, "message": "Hello"},
        headers=auth_headers("wrong-token"),
    )
    assert wrong.status_code == 403
    assert error_code(wrong) == "CSRF_FAILED"

    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0


def test_create_with_valid_csrf_but_no_session_is_401(
    client, app, colleague_id
):
    from tests.helpers import get_csrf

    token = get_csrf(client)
    response = client.post(
        "/api/kudos",
        json={"recipientId": colleague_id, "message": "Hello"},
        headers=auth_headers(token),
    )
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0
