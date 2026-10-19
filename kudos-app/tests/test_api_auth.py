"""Session, CSRF, and authentication tests."""

from __future__ import annotations

import pytest

from app import create_app
from tests.helpers import (
    auth_headers,
    fetch_one,
    get_csrf,
    login,
)


def error_code(response) -> str:
    return response.get_json()["error"]["code"]


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_csrf_endpoint_is_public_and_returns_token(client):
    response = client.get("/api/csrf")
    assert response.status_code == 200
    token = response.get_json()["csrfToken"]
    assert isinstance(token, str)
    assert len(token) >= 32


def test_protected_get_endpoints_require_a_session(client):
    for path in ("/api/me", "/api/users", "/api/kudos", "/api/admin/kudos"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert error_code(response) == "UNAUTHENTICATED"
        assert response.get_json()["error"]["requestId"]
        assert response.headers["X-Request-Id"]


def test_demo_users_are_public_and_have_exactly_one_admin(client):
    response = client.get("/api/demo/users")
    assert response.status_code == 200
    users = response.get_json()["users"]
    assert len(users) == 9
    admins = [user for user in users if user["role"] == "admin"]
    assert len(admins) == 1
    assert admins[0]["name"] == "Morgan Reed"
    assert all("email" not in user for user in users)


def test_demo_users_are_sorted_by_name(client):
    names = [
        user["name"]
        for user in client.get("/api/demo/users").get_json()["users"]
    ]
    assert names == sorted(names, key=str.lower)


def test_login_rotates_csrf_and_persists_session(client, employee_id):
    old_token = get_csrf(client)
    new_token = login(client, employee_id)

    assert new_token != old_token
    me = client.get("/api/me")
    assert me.status_code == 200
    user = me.get_json()["user"]
    assert user["id"] == employee_id
    assert user["role"] == "employee"


def test_old_csrf_token_is_invalid_after_login(client, employee_id, colleague_id):
    old_token = get_csrf(client)
    login(client, employee_id)

    response = client.post(
        "/api/kudos",
        json={"recipientId": colleague_id, "message": "Hello"},
        headers=auth_headers(old_token),
    )
    assert response.status_code == 403
    assert error_code(response) == "CSRF_FAILED"


def test_login_rejects_unknown_user(client):
    token = get_csrf(client)
    response = client.post(
        "/api/demo/session",
        json={"userId": 99999},
        headers=auth_headers(token),
    )
    assert response.status_code == 404
    assert error_code(response) == "USER_NOT_FOUND"


def test_login_rejects_inactive_user(client, app, employee_id):
    from tests.helpers import execute

    execute(app, "UPDATE users SET is_active = 0 WHERE id = ?", (employee_id,))
    token = get_csrf(client)
    response = client.post(
        "/api/demo/session",
        json={"userId": employee_id},
        headers=auth_headers(token),
    )
    assert response.status_code == 404
    assert error_code(response) == "USER_NOT_FOUND"


def test_login_ignores_client_supplied_role(client, employee_id):
    token = get_csrf(client)
    response = client.post(
        "/api/demo/session",
        json={"userId": employee_id, "role": "admin", "isAdmin": True},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "employee"
    assert client.get("/api/me").get_json()["user"]["role"] == "employee"


def test_switching_user_replaces_the_session(client, employee_id, admin_id):
    login(client, employee_id)
    assert client.get("/api/me").get_json()["user"]["role"] == "employee"

    new_token = login(client, admin_id)
    me = client.get("/api/me")
    assert me.get_json()["user"]["role"] == "admin"

    response = client.post(
        "/api/kudos",
        json={"recipientId": employee_id, "message": "Hello"},
        headers=auth_headers(new_token),
    )
    assert response.status_code == 201


def test_logout_requires_csrf_and_clears_the_session(client, employee_id):
    token = login(client, employee_id)

    response = client.delete("/api/demo/session")
    assert response.status_code == 403
    assert error_code(response) == "CSRF_FAILED"
    assert client.get("/api/me").status_code == 200

    response = client.delete(
        "/api/demo/session",
        headers=auth_headers(token),
    )
    assert response.status_code == 204
    assert client.get("/api/me").status_code == 401

    repeat = client.delete(
        "/api/demo/session",
        headers=auth_headers(token),
    )
    assert repeat.status_code == 403
    assert error_code(repeat) == "CSRF_FAILED"


def test_login_requires_csrf(client, employee_id):
    response = client.post(
        "/api/demo/session",
        json={"userId": employee_id},
    )
    assert response.status_code == 403
    assert error_code(response) == "CSRF_FAILED"
    assert client.get("/api/me").status_code == 401


def test_unsafe_request_without_csrf_is_rejected_before_auth(
    client, app, employee_id, colleague_id
):
    response = client.post(
        "/api/kudos",
        json={"recipientId": colleague_id, "message": "Hello"},
    )
    assert response.status_code == 403
    assert error_code(response) == "CSRF_FAILED"
    count = fetch_one(app, "SELECT COUNT(*) AS count FROM kudos")["count"]
    assert count == 0
    assert employee_id  # fixture proves a real seed row exists


def test_valid_csrf_without_session_returns_401(
    client, app, colleague_id
):
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


def test_demo_routes_can_be_disabled(tmp_path):
    disabled_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "disabled-demo-secret",
            "DATABASE": str(tmp_path / "disabled.db"),
            "ALLOW_DEMO_LOGIN": False,
        }
    )
    disabled_client = disabled_app.test_client()
    token = get_csrf(disabled_client)

    users = disabled_client.get("/api/demo/users")
    assert users.status_code == 404
    assert error_code(users) == "NOT_FOUND"

    login_response = disabled_client.post(
        "/api/demo/session",
        json={"userId": 1},
        headers=auth_headers(token),
    )
    assert login_response.status_code == 404
    assert error_code(login_response) == "NOT_FOUND"

    logout_response = disabled_client.delete(
        "/api/demo/session",
        headers=auth_headers(token),
    )
    assert logout_response.status_code == 404
    assert error_code(logout_response) == "NOT_FOUND"

    assert disabled_client.get("/api/csrf").status_code == 200


def test_security_headers_are_present(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert page.headers["Referrer-Policy"] == "no-referrer"

    api_response = client.get("/api/csrf")
    assert api_response.headers["Cache-Control"] == "no-store"
    assert api_response.headers["X-Request-Id"]


def test_method_not_allowed_uses_json_envelope(client, employee_id):
    login(client, employee_id)
    # GET is safe, so this reaches routing and fails on the method rather than
    # being rejected by the CSRF guard.
    response = client.get("/api/demo/session")
    assert response.status_code == 405
    assert error_code(response) == "METHOD_NOT_ALLOWED"


@pytest.mark.parametrize("path", ["/api/does-not-exist"])
def test_unknown_api_route_uses_json_envelope(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"
