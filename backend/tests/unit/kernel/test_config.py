"""AC-20: kernel settings (TASK-005 Design section 8)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest
from pydantic import SecretStr

from abacus.kernel.config import Settings

CONNECTION = (
    "database_url",
    "migrations_database_url",
    "relay_database_url",
    "temporal_target",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)  # no stray .env


def _plain(value: object) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else str(value)


def _explicit_connection_env(monkeypatch: pytest.MonkeyPatch, omit: str | None = None) -> None:
    values = {
        "database_url": "postgresql+asyncpg://app@db.example.test:5432/abacus",
        "migrations_database_url": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
        "relay_database_url": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
        "temporal_target": "temporal.example.test:7233",
    }
    for name in Settings.model_fields:
        if name.startswith("s3_"):
            values[name] = "https://s3.example.test"
    for name, value in values.items():
        if name != omit:
            monkeypatch.setenv(f"ABACUS_{name.upper()}", value)


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_local_and_test_environments_load_with_defaults(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    settings = Settings()
    assert settings.environment == environment
    assert "55432" in _plain(settings.database_url)
    assert "55432" in _plain(settings.migrations_database_url)
    assert "55432" in _plain(settings.relay_database_url)
    assert "abacus_relay" in _plain(settings.relay_database_url)
    assert settings.temporal_target


def test_ac20_environment_defaults_to_local() -> None:
    assert Settings().environment == "local"


def test_ac20_unknown_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "dev")
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_non_local_environment_without_database_url_fails(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("missing", CONNECTION)
def test_ac20_non_local_environment_requires_each_connection_setting(
    monkeypatch: pytest.MonkeyPatch, environment: str, missing: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    _explicit_connection_env(monkeypatch, omit=missing)
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_non_local_environment_with_everything_explicit_loads(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    _explicit_connection_env(monkeypatch)
    settings = Settings()
    assert settings.environment == environment
    assert "db.example.test" in _plain(settings.database_url)
    assert "55432" not in _plain(settings.database_url)
    assert "db.example.test" in _plain(settings.relay_database_url)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_non_local_environment_without_relay_database_url_fails(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    _explicit_connection_env(monkeypatch, omit="relay_database_url")
    with pytest.raises(ValueError, match="relay_database_url"):
        Settings()


def test_ac20_relay_url_is_a_secret_and_never_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    password = secrets.token_hex(8)
    url = f"postgresql+asyncpg://abacus_relay:{password}@localhost:55432/abacus"
    monkeypatch.setenv("ABACUS_RELAY_DATABASE_URL", url)
    settings = Settings()
    assert isinstance(settings.relay_database_url, SecretStr)
    assert settings.relay_database_url.get_secret_value() == url
    for rendered in (repr(settings), str(settings), settings.model_dump_json()):
        assert password not in rendered


def test_ac20_migrations_url_is_a_secret_and_never_in_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = secrets.token_hex(8)
    url = f"postgresql+asyncpg://abacus_owner:{password}@localhost:55432/abacus"
    monkeypatch.setenv("ABACUS_MIGRATIONS_DATABASE_URL", url)
    settings = Settings()
    assert isinstance(settings.migrations_database_url, SecretStr)
    assert settings.migrations_database_url.get_secret_value() == url
    for rendered in (repr(settings), str(settings), settings.model_dump_json()):
        assert password not in rendered


def test_ac20_every_secret_looking_field_is_a_secretstr() -> None:
    settings = Settings()
    secretish = [
        name
        for name in Settings.model_fields
        if any(word in name for word in ("secret", "password", "token"))
    ]
    for name in [*secretish, "migrations_database_url", "relay_database_url"]:
        assert isinstance(getattr(settings, name), SecretStr), name


def test_ac20_env_prefix_is_abacus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_TARGET", "temporal.example.test:7233")
    assert Settings().temporal_target == "temporal.example.test:7233"
    monkeypatch.delenv("ABACUS_TEMPORAL_TARGET")
    monkeypatch.setenv("TEMPORAL_TARGET", "unprefixed.example.test:7233")
    assert Settings().temporal_target != "unprefixed.example.test:7233"


def test_ac20_validation_errors_do_not_echo_input_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaked = f"not-a-number-{secrets.token_hex(8)}"
    monkeypatch.setenv("ABACUS_DATABASE_STATEMENT_TIMEOUT_MS", leaked)
    with pytest.raises(ValueError) as raised:
        Settings()
    assert "database_statement_timeout_ms" in str(raised.value)
    assert leaked not in str(raised.value)
    assert leaked not in repr(raised.value)


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("missing", ["s3_access_key", "s3_secret_key"])
def test_ac20_non_local_environment_requires_the_s3_keys(
    monkeypatch: pytest.MonkeyPatch, environment: str, missing: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    _explicit_connection_env(monkeypatch, omit=missing)
    with pytest.raises(ValueError):
        Settings()
