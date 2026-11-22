"""Shared pytest fixtures.

The environment is configured before importing the app so the test database
never touches the local development SQLite file.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

if os.getenv("TEST_DATABASE_URL"):
    # CI runs the same suite against PostgreSQL to catch dialect-specific bugs.
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    _TMP_DIR = Path(tempfile.mkdtemp(prefix="pricepulse-tests-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["ROBOTS_CHECK_ENABLED"] = "false"
os.environ["TELEGRAM_ENABLED"] = "false"
os.environ["TELEGRAM_BOT_POLLING"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["PUBLIC_BASE_URL"] = "http://testserver"

import pytest
from app.database import Base, SessionLocal, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
