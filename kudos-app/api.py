"""JSON API routes for the Kudos demo.

The blueprint enforces CSRF for every unsafe method before any route handler
runs. Authentication and administrator authorization are enforced by
decorators that read the current role from SQLite.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from auth import (
    UNSAFE_METHODS,
    admin_required,
    csrf_token_matches,
    ensure_csrf_token,
    load_current_user,
    login_required,
    sign_in_demo_user,
    sign_out_demo_user,
)
from db import get_db, transaction
from validation import (
    ApiError,
    parse_limit,
    parse_offset,
    parse_path_id,
    parse_positive_int,
    parse_visibility,
    require_json_object,
    validate_kudos_payload,
)

api = Blueprint("api", __name__, url_prefix="/api")

KUDOS_SELECT = """
    SELECT
        k.id,
        k.message,
        k.created_at,
        k.is_visible,
        g.id   AS giver_id,
        g.name AS giver_name,
        r.id   AS recipient_id,
        r.name AS recipient_name
    FROM kudos AS k
    JOIN users AS g ON g.id = k.giver_id
    JOIN users AS r ON r.id = k.recipient_id
"""


def error_response(
    code: str,
    message: str,
    status: int,
    fields: dict = None,
):
    """Build the single JSON error envelope used by the API."""

    error = {
        "code": code,
        "message": message,
        "requestId": getattr(g, "request_id", None),
    }
    if fields:
        error["fields"] = fields
    response = jsonify({"error": error})
    response.status_code = status
    return response


def _demo_login_enabled() -> bool:
    return bool(current_app.config.get("ALLOW_DEMO_LOGIN"))


def _demo_disabled() -> None:
    raise ApiError(
        code="NOT_FOUND",
        message="Demo identity routes are disabled.",
        status=404,
    )


def _public_user(row, include_role: bool = False) -> dict:
    user = {
        "id": row["id"],
        "name": row["name"],
        "department": row["department"],
    }
    if include_role:
        user["role"] = row["role"]
    return user


def _public_kudos(row) -> dict:
    return {
        "id": row["id"],
        "message": row["message"],
        "createdAt": row["created_at"],
        "giver": {"id": row["giver_id"], "name": row["giver_name"]},
        "recipient": {"id": row["recipient_id"], "name": row["recipient_name"]},
    }


def _admin_kudos(row) -> dict:
    item = _public_kudos(row)
    item["isVisible"] = bool(row["is_visible"])
    return item


def _fetch_kudos(kudos_id: int):
    return get_db().execute(
        KUDOS_SELECT + " WHERE k.id = ?",
        (kudos_id,),
    ).fetchone()


def _fetch_active_user(user_id: int):
    return get_db().execute(
        "SELECT id, name, department, role, is_active "
        "FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


@api.before_request
def protect_unsafe_methods():
    """Reject every unsafe API request without a matching CSRF token.

    This runs before authentication so a forgotten state-changing route is
    still protected. The client obtains or refreshes its token from
    ``GET /api/csrf``.
    """

    if request.method in UNSAFE_METHODS:
        provided = request.headers.get("X-CSRF-Token")
        if not csrf_token_matches(provided):
            return error_response(
                code="CSRF_FAILED",
                message="Security token missing or invalid. Refresh the page and try again.",
                status=403,
            )
    return None


@api.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify({"status": "ok"})


@api.get("/csrf")
def csrf():
    return jsonify({"csrfToken": ensure_csrf_token()})


# ---------------------------------------------------------------------------
# Demo identity (disabled in production by ALLOW_DEMO_LOGIN=0)
# ---------------------------------------------------------------------------


@api.get("/demo/users")
def demo_users():
    if not _demo_login_enabled():
        _demo_disabled()
    rows = get_db().execute(
        "SELECT id, name, department, role, is_active "
        "FROM users WHERE is_active = 1 "
        "ORDER BY name COLLATE NOCASE ASC"
    ).fetchall()
    return jsonify({"users": [_public_user(row, include_role=True) for row in rows]})


@api.post("/demo/session")
def demo_login():
    if not _demo_login_enabled():
        _demo_disabled()

    data = require_json_object(request)
    user_id = parse_positive_int(data.get("userId"), "userId")
    user = _fetch_active_user(user_id)
    if user is None:
        raise ApiError(
            code="USER_NOT_FOUND",
            message="That demo user does not exist or is inactive.",
            status=404,
        )

    new_token = sign_in_demo_user(user["id"])
    current_app.logger.info("demo login user_id=%s", user["id"])
    return jsonify(
        {
            "user": _public_user(user, include_role=True),
            "csrfToken": new_token,
        }
    )


@api.delete("/demo/session")
def demo_logout():
    if not _demo_login_enabled():
        _demo_disabled()
    sign_out_demo_user()
    return "", 204


# ---------------------------------------------------------------------------
# Current user and colleagues
# ---------------------------------------------------------------------------


@api.get("/me")
@login_required
def me():
    user = load_current_user()
    return jsonify({"user": _public_user(user, include_role=True)})


@api.get("/users")
@login_required
def users():
    rows = get_db().execute(
        "SELECT id, name, department, role, is_active "
        "FROM users WHERE is_active = 1 "
        "ORDER BY name COLLATE NOCASE ASC"
    ).fetchall()
    # Roles and email addresses are deliberately not exposed here.
    return jsonify({"users": [_public_user(row) for row in rows]})


# ---------------------------------------------------------------------------
# Employee feed and kudos creation
# ---------------------------------------------------------------------------


@api.get("/kudos")
@login_required
def kudos_feed():
    limit = parse_limit(request.args.get("limit"))
    offset = parse_offset(request.args.get("offset"))

    # Fetch one extra row so we can compute hasMore without COUNT(*).
    rows = get_db().execute(
        KUDOS_SELECT
        + """
        WHERE k.is_visible = 1
        ORDER BY k.created_at DESC, k.id DESC
        LIMIT ? OFFSET ?
        """,
        (limit + 1, offset),
    ).fetchall()

    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    next_offset = offset + len(visible_rows) if has_more else None

    return jsonify(
        {
            "items": [_public_kudos(row) for row in visible_rows],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "hasMore": has_more,
                "nextOffset": next_offset,
            },
        }
    )


@api.post("/kudos")
@login_required
def create_kudos():
    current_user = load_current_user()
    data = require_json_object(request)
    recipient_id, message = validate_kudos_payload(data)

    recipient = _fetch_active_user(recipient_id)
    if recipient is None:
        raise ApiError(
            code="RECIPIENT_NOT_FOUND",
            message="That recipient does not exist or is inactive.",
            status=404,
        )
    if recipient_id == current_user["id"]:
        raise ApiError(
            code="SELF_KUDOS",
            message="You cannot give kudos to yourself.",
            status=400,
        )

    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO kudos (giver_id, recipient_id, message) VALUES (?, ?, ?)",
            (current_user["id"], recipient_id, message),
        )
        kudos_id = cursor.lastrowid

    row = _fetch_kudos(kudos_id)
    if row is None:
        raise ApiError(
            code="INTERNAL_ERROR",
            message="The kudos could not be loaded after creation.",
            status=500,
        )

    current_app.logger.info(
        "kudos created kudos_id=%s giver_id=%s recipient_id=%s",
        kudos_id,
        current_user["id"],
        recipient_id,
    )
    return jsonify({"kudos": _public_kudos(row)}), 201


# ---------------------------------------------------------------------------
# Administrator moderation
# ---------------------------------------------------------------------------


@api.get("/admin/kudos")
@admin_required
def admin_kudos():
    limit = parse_limit(request.args.get("limit"))
    offset = parse_offset(request.args.get("offset"))
    visibility = parse_visibility(request.args.get("visibility"))

    rows = get_db().execute(
        KUDOS_SELECT
        + """
        WHERE (:visibility = 'all'
               OR (:visibility = 'visible' AND k.is_visible = 1)
               OR (:visibility = 'hidden'  AND k.is_visible = 0))
        ORDER BY k.created_at DESC, k.id DESC
        LIMIT :limit OFFSET :offset
        """,
        {
            "visibility": visibility,
            "limit": limit + 1,
            "offset": offset,
        },
    ).fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_offset = offset + len(page_rows) if has_more else None

    return jsonify(
        {
            "items": [_admin_kudos(row) for row in page_rows],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "hasMore": has_more,
                "nextOffset": next_offset,
                "visibility": visibility,
            },
        }
    )


def _set_visibility(kudos_id: int, visible: bool) -> dict:
    actor = load_current_user()
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE kudos SET is_visible = ? WHERE id = ?",
            (1 if visible else 0, kudos_id),
        )
        if cursor.rowcount == 0:
            raise ApiError(
                code="KUDOS_NOT_FOUND",
                message="That kudos does not exist or was already deleted.",
                status=404,
            )

    row = _fetch_kudos(kudos_id)
    if row is None:
        raise ApiError(
            code="KUDOS_NOT_FOUND",
            message="That kudos does not exist or was already deleted.",
            status=404,
        )

    action = "restore" if visible else "hide"
    current_app.logger.info(
        "moderation action=%s kudos_id=%s actor_id=%s",
        action,
        kudos_id,
        actor["id"],
    )
    return _admin_kudos(row)


@api.post("/admin/kudos/<raw_id>/hide")
@admin_required
def hide_kudos(raw_id: str):
    kudos_id = parse_path_id(raw_id)
    return jsonify({"kudos": _set_visibility(kudos_id, visible=False)})


@api.post("/admin/kudos/<raw_id>/restore")
@admin_required
def restore_kudos(raw_id: str):
    kudos_id = parse_path_id(raw_id)
    return jsonify({"kudos": _set_visibility(kudos_id, visible=True)})


@api.delete("/admin/kudos/<raw_id>")
@admin_required
def delete_kudos(raw_id: str):
    kudos_id = parse_path_id(raw_id)
    actor = load_current_user()

    with transaction() as connection:
        cursor = connection.execute("DELETE FROM kudos WHERE id = ?", (kudos_id,))
        if cursor.rowcount == 0:
            raise ApiError(
                code="KUDOS_NOT_FOUND",
                message="That kudos does not exist or was already deleted.",
                status=404,
            )

    current_app.logger.info(
        "moderation action=delete kudos_id=%s actor_id=%s",
        kudos_id,
        actor["id"],
    )
    return "", 204
