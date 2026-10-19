"""Administrator moderation, authorization, and persistence tests."""

from __future__ import annotations

import pytest

from app import create_app
from tests.helpers import (
    auth_headers,
    create_kudos,
    execute,
    fetch_one,
    get_csrf,
    insert_kudos,
    kudos_row,
    login,
    user_id_by_email,
)


def error_code(response) -> str:
    return response.get_json()["error"]["code"]


def hide(client, token: str, kudos_id: int):
    return client.post(
        f"/api/admin/kudos/{kudos_id}/hide",
        headers=auth_headers(token),
    )


def restore(client, token: str, kudos_id: int):
    return client.post(
        f"/api/admin/kudos/{kudos_id}/restore",
        headers=auth_headers(token),
    )


def delete(client, token: str, kudos_id: int):
    return client.delete(
        f"/api/admin/kudos/{kudos_id}",
        headers=auth_headers(token),
    )


def admin_items(client, query: str = "") -> list:
    response = client.get(f"/api/admin/kudos{query}")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["items"]


# ---------------------------------------------------------------------------
# Administrator listing
# ---------------------------------------------------------------------------


def test_admin_list_requires_authentication(client):
    response = client.get("/api/admin/kudos")
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"


def test_employee_cannot_list_moderation_queue(client, employee_id):
    login(client, employee_id)
    response = client.get("/api/admin/kudos")
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_admin_list_includes_visible_and_hidden_kudos(
    client, app, employee_id, colleague_id, admin_id
):
    login(client, admin_id)
    visible = insert_kudos(app, employee_id, colleague_id, "Visible")
    hidden = insert_kudos(
        app, employee_id, colleague_id, "Hidden", is_visible=0
    )

    items = admin_items(client)
    by_id = {item["id"]: item for item in items}
    assert set(by_id) == {visible, hidden}
    assert by_id[visible]["isVisible"] is True
    assert by_id[hidden]["isVisible"] is False
    assert by_id[hidden]["message"] == "Hidden"
    assert all("email" not in item for item in items)


def test_admin_list_filters_by_visibility(
    client, app, employee_id, colleague_id, admin_id
):
    login(client, admin_id)
    visible = insert_kudos(app, employee_id, colleague_id, "Visible")
    hidden = insert_kudos(
        app, employee_id, colleague_id, "Hidden", is_visible=0
    )

    assert {item["id"] for item in admin_items(client)} == {visible, hidden}
    assert {
        item["id"] for item in admin_items(client, "?visibility=all")
    } == {visible, hidden}
    assert [
        item["id"] for item in admin_items(client, "?visibility=visible")
    ] == [visible]
    assert [
        item["id"] for item in admin_items(client, "?visibility=hidden")
    ] == [hidden]


def test_admin_list_is_newest_first(
    client, app, employee_id, colleague_id, admin_id
):
    login(client, admin_id)
    oldest = insert_kudos(
        app,
        employee_id,
        colleague_id,
        "Oldest",
        created_at="2026-01-01T00:00:00.000Z",
    )
    newest = insert_kudos(
        app,
        employee_id,
        colleague_id,
        "Newest",
        created_at="2026-01-02T00:00:00.000Z",
    )

    assert [item["id"] for item in admin_items(client)] == [newest, oldest]


def test_admin_list_paginates_with_the_active_filter(
    client, app, employee_id, colleague_id, admin_id
):
    login(client, admin_id)
    for index in range(3):
        insert_kudos(
            app,
            employee_id,
            colleague_id,
            f"Hidden {index}",
            is_visible=0,
        )
    insert_kudos(app, employee_id, colleague_id, "Visible")

    response = client.get("/api/admin/kudos?visibility=hidden&limit=2")
    data = response.get_json()
    assert len(data["items"]) == 2
    assert data["pagination"] == {
        "limit": 2,
        "offset": 0,
        "hasMore": True,
        "nextOffset": 2,
        "visibility": "hidden",
    }

    second = client.get("/api/admin/kudos?visibility=hidden&limit=2&offset=2")
    second_data = second.get_json()
    assert len(second_data["items"]) == 1
    assert second_data["pagination"]["hasMore"] is False
    assert second_data["pagination"]["nextOffset"] is None


@pytest.mark.parametrize("value", ["ALL", "deleted", "1", "visible,hidden"])
def test_admin_list_rejects_invalid_visibility_filter(
    client, employee_id, admin_id, value
):
    login(client, admin_id)
    response = client.get(f"/api/admin/kudos?visibility={value}")
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "visibility" in response.get_json()["error"]["fields"]


def test_admin_list_rejects_invalid_pagination(client, admin_id):
    login(client, admin_id)
    response = client.get("/api/admin/kudos?limit=999")
    assert response.status_code == 400
    assert "limit" in response.get_json()["error"]["fields"]


# ---------------------------------------------------------------------------
# Server-side authorization
# ---------------------------------------------------------------------------


def test_employees_cannot_moderate_even_by_calling_the_api_directly(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Keep me")
    token = login(client, employee_id)

    responses = [
        hide(client, token, kudos_id),
        restore(client, token, kudos_id),
        delete(client, token, kudos_id),
    ]

    for response in responses:
        assert response.status_code == 403
        assert error_code(response) == "FORBIDDEN"

    row = kudos_row(app, kudos_id)
    assert row is not None
    assert row["is_visible"] == 1
    assert row["message"] == "Keep me"


def test_client_supplied_role_does_not_grant_access(
    client, employee_id
):
    token = login(client, employee_id)

    response = client.get(
        "/api/admin/kudos?role=admin",
        headers={"X-Role": "admin", "X-Is-Admin": "true"},
    )
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"

    hidden = client.post(
        "/api/admin/kudos/1/hide",
        json={"role": "admin", "isAdmin": True},
        headers={**auth_headers(token), "X-Role": "admin"},
    )
    assert hidden.status_code == 403
    assert error_code(hidden) == "FORBIDDEN"


def test_role_is_read_from_the_database_on_every_request(
    client, app, admin_id
):
    login(client, admin_id)
    assert client.get("/api/admin/kudos").status_code == 200

    execute(app, "UPDATE users SET role = 'employee' WHERE id = ?", (admin_id,))
    response = client.get("/api/admin/kudos")
    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"

    execute(app, "UPDATE users SET role = 'admin' WHERE id = ?", (admin_id,))
    assert client.get("/api/admin/kudos").status_code == 200


def test_promoted_employee_gains_access_with_the_existing_session(
    client, app, employee_id
):
    login(client, employee_id)
    assert client.get("/api/admin/kudos").status_code == 403

    execute(app, "UPDATE users SET role = 'admin' WHERE id = ?", (employee_id,))
    assert client.get("/api/admin/kudos").status_code == 200


def test_admin_hide_requires_csrf(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Keep me")
    login(client, admin_id)

    for headers in ({}, auth_headers("wrong-token")):
        response = client.post(
            f"/api/admin/kudos/{kudos_id}/hide",
            headers=headers,
        )
        assert response.status_code == 403
        assert error_code(response) == "CSRF_FAILED"

    assert kudos_row(app, kudos_id)["is_visible"] == 1


def test_admin_restore_requires_csrf(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(
        app, employee_id, colleague_id, "Hidden", is_visible=0
    )
    login(client, admin_id)

    for headers in ({}, auth_headers("wrong-token")):
        response = client.post(
            f"/api/admin/kudos/{kudos_id}/restore",
            headers=headers,
        )
        assert response.status_code == 403
        assert error_code(response) == "CSRF_FAILED"

    assert kudos_row(app, kudos_id)["is_visible"] == 0


def test_admin_delete_requires_csrf(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Keep me")
    login(client, admin_id)

    for headers in ({}, auth_headers("wrong-token")):
        response = client.delete(
            f"/api/admin/kudos/{kudos_id}",
            headers=headers,
        )
        assert response.status_code == 403
        assert error_code(response) == "CSRF_FAILED"

    assert kudos_row(app, kudos_id) is not None


def test_admin_actions_with_valid_csrf_but_no_session_are_401(
    client, app, employee_id, colleague_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Keep me")
    token = get_csrf(client)

    responses = [
        hide(client, token, kudos_id),
        restore(client, token, kudos_id),
        delete(client, token, kudos_id),
    ]
    for response in responses:
        assert response.status_code == 401
        assert error_code(response) == "UNAUTHENTICATED"

    row = kudos_row(app, kudos_id)
    assert row is not None
    assert row["is_visible"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/kudos/1/hide",
        "/api/admin/kudos/1/restore",
        "/api/admin/kudos/1",
    ],
)
def test_state_changing_moderation_routes_reject_get(
    client, employee_id, admin_id, path
):
    login(client, admin_id)
    response = client.get(path)
    assert response.status_code == 405
    assert error_code(response) == "METHOD_NOT_ALLOWED"
    assert "POST" in response.headers["Allow"] or "DELETE" in response.headers["Allow"]


# ---------------------------------------------------------------------------
# Hide and restore: reversible visibility changes
# ---------------------------------------------------------------------------


def test_hide_removes_kudos_from_the_employee_feed_but_keeps_the_row(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Needs review")
    original = kudos_row(app, kudos_id)

    token = login(client, admin_id)
    response = hide(client, token, kudos_id)

    assert response.status_code == 200
    data = response.get_json()["kudos"]
    assert data["id"] == kudos_id
    assert data["isVisible"] is False
    assert data["message"] == "Needs review"

    row = kudos_row(app, kudos_id)
    assert row is not None
    assert row["is_visible"] == 0
    assert row["created_at"] == original["created_at"]
    assert row["message"] == original["message"]
    assert row["giver_id"] == original["giver_id"]
    assert row["recipient_id"] == original["recipient_id"]

    feed = client.get("/api/kudos").get_json()["items"]
    assert all(item["id"] != kudos_id for item in feed)

    admin_list = admin_items(client)
    assert any(item["id"] == kudos_id for item in admin_list)


def test_restore_makes_kudos_visible_again(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(
        app, employee_id, colleague_id, "Restore me", is_visible=0
    )
    original_created_at = kudos_row(app, kudos_id)["created_at"]

    token = login(client, admin_id)
    response = restore(client, token, kudos_id)
    assert response.status_code == 200
    assert response.get_json()["kudos"]["isVisible"] is True

    row = kudos_row(app, kudos_id)
    assert row["is_visible"] == 1
    assert row["created_at"] == original_created_at

    feed = client.get("/api/kudos").get_json()["items"]
    assert any(item["id"] == kudos_id for item in feed)


def test_hide_is_idempotent(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Hide me")
    token = login(client, admin_id)

    first = hide(client, token, kudos_id)
    second = hide(client, token, kudos_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["kudos"]["isVisible"] is False
    assert second.get_json()["kudos"]["isVisible"] is False
    assert kudos_row(app, kudos_id)["is_visible"] == 0


def test_restore_is_idempotent(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Restore me")
    token = login(client, admin_id)

    first = restore(client, token, kudos_id)
    second = restore(client, token, kudos_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["kudos"]["isVisible"] is True
    assert second.get_json()["kudos"]["isVisible"] is True
    assert kudos_row(app, kudos_id)["is_visible"] == 1


def test_admin_may_hide_and_restore_kudos_they_sent(
    client, app, employee_id, admin_id
):
    token = login(client, admin_id)
    created = create_kudos(client, token, employee_id, "My own kudos")
    assert created.status_code == 201
    kudos_id = created.get_json()["kudos"]["id"]

    hidden = hide(client, token, kudos_id)
    assert hidden.status_code == 200
    assert hidden.get_json()["kudos"]["isVisible"] is False

    # Even the administrator does not see hidden kudos in the employee feed.
    feed_ids = {
        item["id"] for item in client.get("/api/kudos").get_json()["items"]
    }
    assert kudos_id not in feed_ids

    restored = restore(client, token, kudos_id)
    assert restored.status_code == 200
    assert restored.get_json()["kudos"]["isVisible"] is True


@pytest.mark.parametrize("action", ["hide", "restore", "delete"])
def test_moderation_missing_kudos_returns_404(
    client, admin_id, action
):
    token = login(client, admin_id)
    call = {"hide": hide, "restore": restore, "delete": delete}[action]

    response = call(client, token, 999999)
    assert response.status_code == 404
    assert error_code(response) == "KUDOS_NOT_FOUND"


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "1.5"])
def test_moderation_rejects_invalid_path_ids(client, admin_id, raw_id):
    token = login(client, admin_id)
    response = client.post(
        f"/api/admin/kudos/{raw_id}/hide",
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "id" in response.get_json()["error"]["fields"]


# ---------------------------------------------------------------------------
# Permanent deletion
# ---------------------------------------------------------------------------


def test_delete_permanently_removes_the_row(
    client, app, employee_id, colleague_id, admin_id
):
    kept = insert_kudos(app, employee_id, colleague_id, "Keep")
    removed = insert_kudos(app, employee_id, colleague_id, "Remove")
    token = login(client, admin_id)

    response = delete(client, token, removed)
    assert response.status_code == 204
    assert response.get_data() == b""

    assert kudos_row(app, removed) is None
    assert kudos_row(app, kept) is not None

    feed_ids = {
        item["id"] for item in client.get("/api/kudos").get_json()["items"]
    }
    assert removed not in feed_ids
    assert kept in feed_ids

    admin_ids = {item["id"] for item in admin_items(client)}
    assert removed not in admin_ids
    assert kept in admin_ids


def test_deleting_a_hidden_kudos_removes_it_from_the_moderation_queue(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(
        app, employee_id, colleague_id, "Hidden", is_visible=0
    )
    token = login(client, admin_id)

    assert delete(client, token, kudos_id).status_code == 204
    assert admin_items(client) == []
    assert kudos_row(app, kudos_id) is None


def test_deleting_twice_returns_404(
    client, app, employee_id, colleague_id, admin_id
):
    kudos_id = insert_kudos(app, employee_id, colleague_id, "Remove")
    token = login(client, admin_id)

    assert delete(client, token, kudos_id).status_code == 204
    second = delete(client, token, kudos_id)
    assert second.status_code == 404
    assert error_code(second) == "KUDOS_NOT_FOUND"


# ---------------------------------------------------------------------------
# Persistence across application restarts
# ---------------------------------------------------------------------------


def test_moderation_changes_survive_an_application_restart(tmp_path):
    database = str(tmp_path / "restart.db")

    def new_app():
        application = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "restart-secret",
                "DATABASE": database,
                "ALLOW_DEMO_LOGIN": True,
            }
        )
        return application

    first_app = new_app()
    alice = user_id_by_email(first_app, "alice.ng@example.internal")
    ben = user_id_by_email(first_app, "ben.okafor@example.internal")
    admin = user_id_by_email(first_app, "morgan.reed@example.internal")

    hidden_id = insert_kudos(first_app, alice, ben, "Hidden after restart")
    deleted_id = insert_kudos(first_app, alice, ben, "Deleted after restart")
    visible_id = insert_kudos(first_app, alice, ben, "Visible after restart")
    original_created_at = kudos_row(first_app, hidden_id)["created_at"]

    first_client = first_app.test_client()
    token = login(first_client, admin)
    assert hide(first_client, token, hidden_id).status_code == 200
    assert delete(first_client, token, deleted_id).status_code == 204

    second_app = new_app()
    second_client = second_app.test_client()
    second_token = login(
        second_client,
        user_id_by_email(second_app, "morgan.reed@example.internal"),
    )

    items = admin_items(second_client)
    by_id = {item["id"]: item for item in items}
    assert by_id[hidden_id]["isVisible"] is False
    assert by_id[visible_id]["isVisible"] is True
    assert deleted_id not in by_id

    assert kudos_row(second_app, deleted_id) is None
    assert kudos_row(second_app, hidden_id)["created_at"] == original_created_at

    employee_client = second_app.test_client()
    login(
        employee_client,
        user_id_by_email(second_app, "alice.ng@example.internal"),
    )
    feed_ids = {
        item["id"]
        for item in employee_client.get("/api/kudos").get_json()["items"]
    }
    assert hidden_id not in feed_ids
    assert visible_id in feed_ids

    restored = restore(second_client, second_token, hidden_id)
    assert restored.status_code == 200
    assert restored.get_json()["kudos"]["isVisible"] is True

    third_app = new_app()
    third_client = third_app.test_client()
    login(
        third_client,
        user_id_by_email(third_app, "alice.ng@example.internal"),
    )
    feed_ids = {
        item["id"]
        for item in third_client.get("/api/kudos").get_json()["items"]
    }
    assert hidden_id in feed_ids
    assert deleted_id not in feed_ids
    count = fetch_one(third_app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 2
