"""Demo session, role authorization, and CSRF helpers.

The session stores only the selected user's ID and a CSRF token. The role is
read from the database on every request, so a changed role takes effect
immediately and a client-supplied role can never influence authorization.
"""

from __future__ import annotations

import hmac
import secrets
from functools import wraps
from typing import Callable, Optional

from flask import g, session

from db import get_db
from validation import ApiError

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_SESSION_KEY = "csrf_token"
USER_SESSION_KEY = "user_id"


def ensure_csrf_token() -> str:
    """Return the session CSRF token, creating one if necessary."""

    token = session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def rotate_csrf_token() -> str:
    """Replace the session CSRF token and return the new value."""

    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def csrf_token_matches(provided: Optional[str]) -> bool:
    """Compare a client token with the session token in constant time."""

    expected = session.get(CSRF_SESSION_KEY)
    if not isinstance(expected, str) or not expected:
        return False
    if not isinstance(provided, str) or not provided:
        return False
    return hmac.compare_digest(expected, provided)


def load_current_user():
    """Load the session user from the database, or return None.

    The result is cached on ``g`` for the duration of one request only.
    """

    if "current_user" in g:
        return g.current_user

    user_id = session.get(USER_SESSION_KEY)
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        return None

    row = get_db().execute(
        "SELECT id, name, department, role, is_active "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if row is None or not row["is_active"]:
        # The selected account no longer exists or was deactivated.
        session.pop(USER_SESSION_KEY, None)
        return None

    g.current_user = row
    return row


def login_required(view: Callable) -> Callable:
    """Reject requests without a valid demo session."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if load_current_user() is None:
            raise ApiError(
                code="UNAUTHENTICATED",
                message="Please choose a demo user to continue.",
                status=401,
            )
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable) -> Callable:
    """Reject requests unless the current database role is ``admin``.

    This deliberately re-reads the role; it never trusts the session or a
    request field for authorization.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        user = load_current_user()
        if user is None:
            raise ApiError(
                code="UNAUTHENTICATED",
                message="Please choose a demo user to continue.",
                status=401,
            )
        if user["role"] != "admin":
            raise ApiError(
                code="FORBIDDEN",
                message="Administrator role required.",
                status=403,
            )
        return view(*args, **kwargs)

    return wrapped


def sign_in_demo_user(user_id: int) -> str:
    """Start a fresh demo session for ``user_id`` and rotate CSRF.

    Clearing the session prevents session fixation and discards the previous
    user's state. The caller must already have checked that the user exists.
    """

    session.clear()
    session[USER_SESSION_KEY] = user_id
    session.permanent = True
    return rotate_csrf_token()


def sign_out_demo_user() -> None:
    """Clear the demo session, including the CSRF token."""

    session.clear()
