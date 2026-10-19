"""Kudos demo application factory and HTML entry point.

Run locally with::

    python app.py

The app binds to 127.0.0.1 by default and uses a local SQLite file.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

from api import api, error_response
from db import init_app as init_database
from validation import ApiError, MAX_REQUEST_BYTES

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "data" / "kudos.db"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _error_code_for_http(status: int) -> str:
    return {
        400: "VALIDATION_ERROR",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        500: "INTERNAL_ERROR",
    }.get(status, "HTTP_ERROR")


def _http_message(status: int) -> str:
    return {
        400: "The request could not be processed.",
        401: "Please choose a demo user to continue.",
        403: "You do not have permission to perform that action.",
        404: "The requested resource was not found.",
        405: "That HTTP method is not allowed for this route.",
        413: "The request body is too large.",
        500: "An unexpected error occurred.",
    }.get(status, "The request could not be processed.")


def create_app(test_config: Optional[dict] = None) -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)

    configured_secret = os.environ.get("SECRET_KEY")
    secret_key = configured_secret or secrets.token_hex(32)
    database_path = os.environ.get("KUDOS_DB_PATH", str(DEFAULT_DATABASE))

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE=database_path,
        ALLOW_DEMO_LOGIN=_env_bool("ALLOW_DEMO_LOGIN", True),
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_env_bool("SESSION_COOKIE_SECURE", False),
    )

    if test_config is not None:
        app.config.update(test_config)

    app.json.sort_keys = False
    app.logger.setLevel(logging.INFO)

    if not configured_secret and "SECRET_KEY" not in (test_config or {}):
        app.logger.warning(
            "SECRET_KEY is not set. Using an ephemeral key; demo sessions and "
            "CSRF tokens will reset when the process restarts."
        )

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_database(app)
    app.register_blueprint(api)

    @app.before_request
    def assign_request_context():
        g.request_id = uuid.uuid4().hex
        g.request_started = time.monotonic()

    @app.after_request
    def add_response_headers(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        started = getattr(g, "request_started", None)
        duration_ms = (
            round((time.monotonic() - started) * 1000, 1)
            if started is not None
            else None
        )
        app.logger.info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s user_id=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            getattr(g, "request_id", None),
            session.get("user_id"),
        )
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_response(
            code=error.code,
            message=error.message,
            status=error.status,
            fields=error.fields,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        if not request.path.startswith("/api/"):
            return error
        status = error.code or 500
        response = error_response(
            code=_error_code_for_http(status),
            message=_http_message(status),
            status=status,
        )
        allow = error.get_response().headers.get("Allow")
        if allow:
            response.headers["Allow"] = allow
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        # Let pytest and the development debugger show the real traceback.
        if app.config.get("TESTING"):
            raise error

        app.logger.exception(
            "unhandled error request_id=%s path=%s",
            getattr(g, "request_id", None),
            request.path,
        )
        if request.path.startswith("/api/"):
            return error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred. Please try again.",
                status=500,
            )
        return "An unexpected error occurred.", 500

    return app


def main() -> None:
    debug = _env_bool("KUDOS_DEBUG", False)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))

    app = create_app()
    if debug:
        app.logger.warning(
            "KUDOS_DEBUG is enabled. The Flask debugger must never be used outside local development."
        )
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
