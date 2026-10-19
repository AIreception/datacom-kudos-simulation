"""Input validation and API error types.

The server is always authoritative. Client-side checks only improve the user
experience; every rule in this module is enforced again on the server.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

from flask import Request
from werkzeug.exceptions import BadRequest

MAX_MESSAGE_LENGTH = 500
MAX_REQUEST_BYTES = 16 * 1024
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
VISIBILITY_VALUES = {"all", "visible", "hidden"}

_ALLOWED_CONTROL_CHARACTERS = {"\n", "\t"}
_UNSIGNED_INTEGER = re.compile(r"^[0-9]+$")


class ApiError(Exception):
    """An error that is safe to return to an API client."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        fields: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}


class ValidationError(ApiError):
    """A field-level input validation failure."""

    def __init__(self, fields: Dict[str, str], message: Optional[str] = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message or "Please correct the highlighted fields.",
            status=400,
            fields=fields,
        )


def _field_error(field: str, message: str) -> ValidationError:
    return ValidationError({field: message})


def parse_positive_int(value: Any, field: str) -> int:
    """Accept only real JSON integers greater than zero.

    ``bool`` is a subclass of ``int`` in Python, so it must be rejected
    explicitly. Strings are rejected because the API contract requires a JSON
    integer.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise _field_error(field, "Must be a positive integer.")
    if value <= 0:
        raise _field_error(field, "Must be a positive integer.")
    return value


def parse_path_id(raw: str, field: str = "id") -> int:
    """Parse a positive integer from a URL path segment."""

    if not isinstance(raw, str) or not _UNSIGNED_INTEGER.fullmatch(raw):
        raise _field_error(field, "Must be a positive integer.")
    value = int(raw)
    if value <= 0:
        raise _field_error(field, "Must be a positive integer.")
    return value


def parse_query_int(
    raw: Optional[str],
    field: str,
    default: int,
    minimum: int,
    maximum: Optional[int] = None,
) -> int:
    """Parse an unsigned query-string integer with bounds."""

    if raw is None or raw == "":
        return default
    if not _UNSIGNED_INTEGER.fullmatch(raw):
        raise _field_error(field, f"Must be an integer of at least {minimum}.")
    value = int(raw)
    if value < minimum:
        raise _field_error(field, f"Must be an integer of at least {minimum}.")
    if maximum is not None and value > maximum:
        raise _field_error(field, f"Must be an integer no greater than {maximum}.")
    return value


def parse_limit(raw: Optional[str]) -> int:
    return parse_query_int(
        raw,
        field="limit",
        default=DEFAULT_PAGE_SIZE,
        minimum=1,
        maximum=MAX_PAGE_SIZE,
    )


def parse_offset(raw: Optional[str]) -> int:
    return parse_query_int(
        raw,
        field="offset",
        default=0,
        minimum=0,
    )


def parse_visibility(raw: Optional[str]) -> str:
    value = "all" if raw is None or raw == "" else raw
    if value not in VISIBILITY_VALUES:
        raise _field_error(
            "visibility",
            "Must be one of: all, visible, hidden.",
        )
    return value


def validate_message(value: Any) -> str:
    """Trim and validate a kudos message.

    Length is measured in Unicode code points, matching JavaScript's
    ``Array.from(text).length`` and SQLite's ``length()`` for text.
    """

    if not isinstance(value, str):
        raise _field_error("message", "Message must be text.")
    trimmed = value.strip()
    if not trimmed:
        raise _field_error("message", "Message cannot be empty.")
    if len(trimmed) > MAX_MESSAGE_LENGTH:
        raise _field_error(
            "message",
            f"Message must be {MAX_MESSAGE_LENGTH} characters or fewer.",
        )
    for character in trimmed:
        if (
            unicodedata.category(character) == "Cc"
            and character not in _ALLOWED_CONTROL_CHARACTERS
        ):
            raise _field_error(
                "message",
                "Message contains unsupported control characters.",
            )
    return trimmed


def validate_kudos_payload(data: Dict[str, Any]) -> tuple:
    """Validate a kudos creation body and return (recipient_id, message).

    Both fields are checked so the client can show all problems at once.
    """

    fields: Dict[str, str] = {}
    recipient_id: Optional[int] = None
    message: Optional[str] = None

    try:
        recipient_id = parse_positive_int(data.get("recipientId"), "recipientId")
    except ValidationError as error:
        fields.update(error.fields)

    try:
        message = validate_message(data.get("message"))
    except ValidationError as error:
        fields.update(error.fields)

    if fields:
        raise ValidationError(fields)

    return recipient_id, message


def require_json_object(request: Request) -> Dict[str, Any]:
    """Return a JSON object body or raise a client-safe error."""

    if not request.is_json:
        raise ApiError(
            code="INVALID_JSON",
            message="Request body must be JSON with Content-Type: application/json.",
            status=400,
        )
    try:
        data = request.get_json(silent=False)
    except BadRequest:
        raise ApiError(
            code="INVALID_JSON",
            message="Request body contains invalid JSON.",
            status=400,
        )
    if not isinstance(data, dict):
        raise ApiError(
            code="INVALID_JSON",
            message="Request body must be a JSON object.",
            status=400,
        )
    return data
