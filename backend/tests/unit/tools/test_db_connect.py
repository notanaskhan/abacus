"""G-09 for the operator tools (P-08-T21 security review): `abacus_tools.db_connect` gives
asyncpg the app's TLS decision: verify-full outside local and test, plain locally."""

from __future__ import annotations

import ssl

import pytest

from abacus.kernel.db_tls import InsecureDatabaseUrl
from abacus_tools.db_connect import tls_for

OPS = "postgresql+asyncpg://abacus_ops:pw@db.example.test:5432/abacus"


def test_a_staging_ops_connection_verifies_the_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "staging")
    monkeypatch.delenv("ABACUS_DATABASE_CA_FILE", raising=False)
    tls = tls_for(OPS)
    assert isinstance(tls.ssl, ssl.SSLContext)
    assert tls.ssl.verify_mode == ssl.CERT_REQUIRED and tls.ssl.check_hostname
    assert tls.url.startswith("postgresql://")  # asyncpg's own scheme


def test_a_staging_dsn_turning_tls_off_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "production")
    with pytest.raises(InsecureDatabaseUrl):
        tls_for(f"{OPS}?sslmode=disable")


def test_a_local_connection_stays_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "local")
    monkeypatch.delenv("ABACUS_DATABASE_CA_FILE", raising=False)
    assert tls_for("postgresql://u:p@127.0.0.1:55432/abacus").ssl is False


def test_the_configured_bundle_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "staging")
    monkeypatch.setenv("ABACUS_DATABASE_CA_FILE", "/nonexistent/rds-bundle.pem")
    with pytest.raises(FileNotFoundError):
        tls_for(OPS)
