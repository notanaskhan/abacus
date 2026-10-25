"""G-09 (ASVS 1.9.2, 9.2.3): the database client verifies the server's certificate whenever TLS
is in use; local and test connections without TLS keep working."""

from __future__ import annotations

import ssl
from pathlib import Path

import pytest

from abacus.kernel import db_tls
from abacus.kernel.config import Settings
from abacus.kernel.db import session as db_session
from abacus.kernel.db_tls import InsecureDatabaseUrl, database_tls, requested_mode

BASE = "postgresql+asyncpg://app:pw@db.example.test:5432/abacus"


def _verifies(context: ssl.SSLContext | bool) -> None:
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_local_without_tls_stays_plain() -> None:
    tls = database_tls(BASE, local=True, ca_file=None)
    assert tls.ssl is False
    assert tls.url == BASE


@pytest.mark.parametrize("off", ["sslmode=disable", "ssl=disable", "ssl=false"])
def test_local_may_turn_tls_off(off: str) -> None:
    tls = database_tls(f"{BASE}?{off}", local=True, ca_file=None)
    assert tls.ssl is False
    assert "ssl" not in tls.url


@pytest.mark.parametrize(
    "mode", ["sslmode=require", "sslmode=prefer", "sslmode=verify-ca", "ssl=require", "ssl=true"]
)
def test_any_requested_tls_mode_is_upgraded_to_verify_full(mode: str) -> None:
    tls = database_tls(f"{BASE}?{mode}&application_name=x", local=True, ca_file=None)
    _verifies(tls.ssl)
    # the DSN's own parameters never reach the driver to override the context
    assert "ssl" not in tls.url
    assert "application_name=x" in tls.url


@pytest.mark.parametrize("url", [BASE, f"{BASE}?sslmode=require", f"{BASE}?ssl=prefer"])
def test_outside_local_tls_is_always_on_and_verified(url: str) -> None:
    _verifies(database_tls(url, local=False, ca_file=None).ssl)


@pytest.mark.parametrize("off", ["sslmode=disable", "ssl=disable", "ssl=false"])
def test_outside_local_a_dsn_turning_tls_off_is_refused(off: str) -> None:
    with pytest.raises(InsecureDatabaseUrl):
        database_tls(f"{BASE}?{off}", local=False, ca_file=None)


def test_the_configured_ca_bundle_is_the_one_trusted(tmp_path: Path) -> None:
    missing = tmp_path / "absent.pem"
    with pytest.raises(FileNotFoundError):
        database_tls(BASE, local=False, ca_file=str(missing))


def test_a_ca_bundle_turns_tls_on_locally_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[str | None] = []

    def fake(ca_file: str | None) -> ssl.SSLContext:
        seen.append(ca_file)
        return ssl.create_default_context()

    monkeypatch.setattr(db_tls, "verifying_context", fake)
    bundle = str(tmp_path / "bundle.pem")
    tls = database_tls(BASE, local=True, ca_file=bundle)
    assert isinstance(tls.ssl, ssl.SSLContext)
    assert seen == [bundle]


def test_sslmode_wins_over_ssl() -> None:
    assert requested_mode(f"{BASE}?ssl=require&sslmode=disable") == "disable"


def test_every_engine_gets_the_tls_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_create(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db_session, "create_async_engine", fake_create)
    db_session._create_engine(f"{BASE}?sslmode=require")  # pyright: ignore[reportPrivateUsage] -- the engine factory under test
    connect_args = captured["connect_args"]
    assert isinstance(connect_args, dict)
    _verifies(connect_args["ssl"])  # pyright: ignore[reportUnknownArgumentType] -- a dict of kwargs
    assert "ssl" not in str(captured["url"])

    db_session._create_engine(BASE)  # pyright: ignore[reportPrivateUsage] -- the engine factory under test
    connect_args = captured["connect_args"]
    assert isinstance(connect_args, dict)
    assert connect_args["ssl"] is False  # the test environment, no TLS asked for


def test_settings_carry_the_ca_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_DATABASE_CA_FILE", "/etc/ssl/rds/global-bundle.pem")
    assert Settings().database_ca_file == "/etc/ssl/rds/global-bundle.pem"
