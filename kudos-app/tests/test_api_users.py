"""Colleague list tests."""

from __future__ import annotations

from tests.helpers import execute, login


def test_colleague_list_requires_session(client):
    assert client.get("/api/users").status_code == 401


def test_colleague_list_is_sorted_and_excludes_private_fields(
    client, employee_id
):
    login(client, employee_id)
    response = client.get("/api/users")
    assert response.status_code == 200

    users = response.get_json()["users"]
    names = [user["name"] for user in users]
    assert names == sorted(names, key=str.lower)
    assert len(users) == 9

    for user in users:
        assert set(user) == {"id", "name", "department"}
        assert "email" not in user
        assert "role" not in user

    assert any(user["id"] == employee_id for user in users)


def test_inactive_colleagues_are_excluded(client, app, employee_id, colleague_id):
    execute(app, "UPDATE users SET is_active = 0 WHERE id = ?", (colleague_id,))
    login(client, employee_id)

    users = client.get("/api/users").get_json()["users"]
    assert all(user["id"] != colleague_id for user in users)
    assert len(users) == 8


def test_admin_is_listed_as_a_colleague_without_exposing_role(
    client, employee_id, admin_id
):
    login(client, employee_id)
    users = client.get("/api/users").get_json()["users"]
    admin = next(user for user in users if user["id"] == admin_id)
    assert admin["name"] == "Morgan Reed"
    assert set(admin) == {"id", "name", "department"}
