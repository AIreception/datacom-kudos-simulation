"""Pytest fixtures for the Kudos demo."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from tests.helpers import user_id_by_email  # noqa: E402


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE": str(tmp_path / "test-kudos.db"),
            "ALLOW_DEMO_LOGIN": True,
        }
    )
    application.logger.setLevel(logging.WARNING)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def employee_id(app):
    return user_id_by_email(app, "alice.ng@example.internal")


@pytest.fixture
def colleague_id(app):
    return user_id_by_email(app, "ben.okafor@example.internal")


@pytest.fixture
def admin_id(app):
    return user_id_by_email(app, "morgan.reed@example.internal")
