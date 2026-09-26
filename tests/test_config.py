"""
Tests for app.core.config.Settings.

`jwt_secret` used to have a hardcoded default ("change-me-in-production"),
so the app would boot with a publicly-known, insecure JWT signing secret if
JWT_SECRET was never set. It is now a required field with no default, so
Settings() must fail loudly at construction time if JWT_SECRET is missing.

This test constructs a *fresh* Settings instance directly, rather than
reloading the app.core.config module (which the rest of the test suite
depends on via the module-level `settings` singleton and its real .env
file). `_env_file=None` disables pydantic-settings' own .env file loading
for this one instance, and `monkeypatch.delenv` removes JWT_SECRET from the
process environment for the duration of the test - together these ensure
no value can reach the field from any source, which is what actually
proves the field has no hardcoded default.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_requires_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("jwt_secret",) and error["type"] == "missing" for error in errors)


def test_settings_requires_gim_database_url_and_emisor(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.delenv("GIM_DATABASE_URL", raising=False)
    monkeypatch.delenv("GIM_EMISOR_RESIDENT_ID", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    missing = {error["loc"] for error in exc_info.value.errors() if error["type"] == "missing"}
    assert ("gim_database_url",) in missing
    assert ("gim_emisor_resident_id",) in missing


def test_settings_gim_defaults(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("GIM_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("GIM_EMISOR_RESIDENT_ID", "5")
    monkeypatch.delenv("GIM_ENTRY_ID_REVISION", raising=False)
    monkeypatch.delenv("TEST_GIM_DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.gim_emisor_resident_id == 5
    assert settings.gim_entry_id_revision == 813
    assert settings.test_gim_database_url == "postgresql+asyncpg://gim_test:gim_test@localhost:5434/gim_test"
