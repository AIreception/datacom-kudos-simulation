"""Unit tests for the server-side product rules."""

from __future__ import annotations

import pytest

from validation import (
    ApiError,
    ValidationError,
    parse_limit,
    parse_offset,
    parse_path_id,
    parse_positive_int,
    parse_visibility,
    validate_kudos_payload,
    validate_message,
)


class TestMessageValidation:
    def test_trims_leading_and_trailing_whitespace(self):
        assert validate_message("  Thank you  \n") == "Thank you"

    def test_accepts_one_character(self):
        assert validate_message("a") == "a"

    def test_accepts_exactly_500_code_points(self):
        message = "a" * 500
        assert validate_message(message) == message

    def test_accepts_500_emoji_by_code_point_count(self):
        message = "😀" * 500
        assert validate_message(message) == message

    @pytest.mark.parametrize("value", ["", "   ", "\n\t  "])
    def test_rejects_empty_or_whitespace_only(self, value):
        with pytest.raises(ValidationError) as exc:
            validate_message(value)
        assert "message" in exc.value.fields

    def test_rejects_501_characters(self):
        with pytest.raises(ValidationError) as exc:
            validate_message("a" * 501)
        assert "message" in exc.value.fields

    @pytest.mark.parametrize("value", [None, 123, [], {}])
    def test_rejects_non_strings(self, value):
        with pytest.raises(ValidationError) as exc:
            validate_message(value)
        assert "message" in exc.value.fields

    @pytest.mark.parametrize("value", ["hello\x00world", "bell\x07", "del\x7f"])
    def test_rejects_control_characters_except_newline_and_tab(self, value):
        with pytest.raises(ValidationError) as exc:
            validate_message(value)
        assert "message" in exc.value.fields

    def test_allows_newline_and_tab(self):
        assert validate_message("Line one\nLine two\tend") == "Line one\nLine two\tend"

    def test_preserves_internal_whitespace(self):
        assert validate_message("  a   b  ") == "a   b"


class TestIntegerValidation:
    @pytest.mark.parametrize("value", [1, 2, 999])
    def test_accepts_positive_integers(self, value):
        assert parse_positive_int(value, "recipientId") == value

    @pytest.mark.parametrize("value", [0, -1, True, False, "1", 1.0, None])
    def test_rejects_non_positive_or_non_integer_values(self, value):
        with pytest.raises(ValidationError) as exc:
            parse_positive_int(value, "recipientId")
        assert "recipientId" in exc.value.fields

    @pytest.mark.parametrize("raw,expected", [("1", 1), ("42", 42)])
    def test_parses_positive_path_ids(self, raw, expected):
        assert parse_path_id(raw) == expected

    @pytest.mark.parametrize("raw", ["0", "-1", "abc", "1.5", "", " 1"])
    def test_rejects_invalid_path_ids(self, raw):
        with pytest.raises(ValidationError) as exc:
            parse_path_id(raw)
        assert "id" in exc.value.fields


class TestPaginationValidation:
    def test_limit_defaults_to_twenty(self):
        assert parse_limit(None) == 20

    def test_limit_accepts_bounds(self):
        assert parse_limit("1") == 1
        assert parse_limit("50") == 50

    @pytest.mark.parametrize("raw", ["0", "51", "-1", "abc", "1.5"])
    def test_limit_rejects_invalid_values(self, raw):
        with pytest.raises(ValidationError) as exc:
            parse_limit(raw)
        assert "limit" in exc.value.fields

    def test_offset_defaults_to_zero(self):
        assert parse_offset(None) == 0

    def test_offset_accepts_large_values(self):
        assert parse_offset("1000") == 1000

    @pytest.mark.parametrize("raw", ["-1", "abc", "1.5"])
    def test_offset_rejects_invalid_values(self, raw):
        with pytest.raises(ValidationError) as exc:
            parse_offset(raw)
        assert "offset" in exc.value.fields


class TestVisibilityValidation:
    def test_defaults_to_all(self):
        assert parse_visibility(None) == "all"
        assert parse_visibility("") == "all"

    @pytest.mark.parametrize("value", ["all", "visible", "hidden"])
    def test_accepts_documented_values(self, value):
        assert parse_visibility(value) == value

    @pytest.mark.parametrize("value", ["ALL", "deleted", "visible,hidden", "1"])
    def test_rejects_other_values(self, value):
        with pytest.raises(ValidationError) as exc:
            parse_visibility(value)
        assert "visibility" in exc.value.fields


class TestKudosPayload:
    def test_returns_recipient_and_trimmed_message(self):
        recipient_id, message = validate_kudos_payload(
            {"recipientId": 2, "message": "  Thanks  "}
        )
        assert recipient_id == 2
        assert message == "Thanks"

    def test_reports_both_fields_when_both_are_invalid(self):
        with pytest.raises(ValidationError) as exc:
            validate_kudos_payload({"recipientId": "2", "message": ""})
        assert set(exc.value.fields) == {"recipientId", "message"}

    def test_api_error_carries_status_and_code(self):
        error = ApiError("TEST", "Test message", status=418)
        assert error.code == "TEST"
        assert error.status == 418
        assert error.fields == {}
