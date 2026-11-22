"""Configuration helpers that are easy to get wrong across platforms."""

from __future__ import annotations

from app.config import Settings


def test_database_url_accepts_render_and_heroku_prefixes():
    settings = Settings(database_url="postgres://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"

    settings = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_database_url_keeps_explicit_driver():
    settings = Settings(database_url="postgresql+psycopg://user:pass@host/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host/db"


def test_telegram_allowed_ids_parsing():
    settings = Settings(telegram_allowed_user_ids=" 1, 22;33,not-a-number, -44 ")
    assert settings.telegram_allowed_id_set == {1, 22, 33, -44}
