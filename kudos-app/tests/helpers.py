"""Shared helpers for the API test suite."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from db import get_db


def get_csrf(client) -> str:
    response = client.get("/api/csrf")
    assert response.status_code == 200
    data = response.get_json()
    assert "csrfToken" in data
    return data["csrfToken"]


def auth_headers(token: Optional[str]) -> dict:
    if token is None:
        return {}
    return {"X-CSRF-Token": token}


def login(client, user_id: int) -> str:
    """Sign in as a seeded demo user and return the rotated CSRF token."""

    token = get_csrf(client)
    response = client.post(
        "/api/demo/session",
        json={"userId": user_id},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert data["user"]["id"] == user_id
    return data["csrfToken"]


def create_kudos(
    client,
    token: str,
    recipient_id: int,
    message: str = "Thank you for your help!",
):
    return client.post(
        "/api/kudos",
        json={"recipientId": recipient_id, "message": message},
        headers=auth_headers(token),
    )


def user_id_by_email(app, email: str) -> int:
    with app.app_context():
        row = get_db().execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        assert row is not None, f"Seed user {email} was not found"
        return row["id"]


def execute(app, sql: str, params: Iterable[Any] = ()):
    """Execute a write against the test database and commit it."""

    with app.app_context():
        connection = get_db()
        cursor = connection.execute(sql, tuple(params))
        connection.commit()
        return cursor.rowcount


def fetch_one(app, sql: str, params: Iterable[Any] = ()):
    with app.app_context():
        return get_db().execute(sql, tuple(params)).fetchone()


def fetch_all(app, sql: str, params: Iterable[Any] = ()):
    with app.app_context():
        return get_db().execute(sql, tuple(params)).fetchall()


def kudos_row(app, kudos_id: int):
    return fetch_one(
        app,
        "SELECT id, giver_id, recipient_id, message, is_visible, created_at "
        "FROM kudos WHERE id = ?",
        (kudos_id,),
    )


def insert_kudos(
    app,
    giver_id: int,
    recipient_id: int,
    message: str = "Seeded test kudos",
    is_visible: int = 1,
    created_at: Optional[str] = None,
) -> int:
    """Insert a kudos directly for setup where the API is not the subject."""

    with app.app_context():
        connection = get_db()
        if created_at is None:
            cursor = connection.execute(
                "INSERT INTO kudos (giver_id, recipient_id, message, is_visible) "
                "VALUES (?, ?, ?, ?)",
                (giver_id, recipient_id, message, is_visible),
            )
        else:
            cursor = connection.execute(
                "INSERT INTO kudos "
                "(giver_id, recipient_id, message, is_visible, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (giver_id, recipient_id, message, is_visible, created_at),
            )
        connection.commit()
        return cursor.lastrowid
