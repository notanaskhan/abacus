"""Q-01-T20: the database bootstrap task's inputs (no database: the SQL is bootstrap.sql's own,
run by the compose init and the test fixtures)."""

from __future__ import annotations

import pytest

from abacus_tools import db_bootstrap

GOOD = "x" * 40
SHORT = "y" * 12


def _env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    values = {
        "ABACUS_DB_HOST": "db.internal.example.test",
        "ABACUS_DB_MASTER_USER": "abacus_admin",
        "ABACUS_DB_MASTER_PASSWORD": "p@ss/word?with&chars",
        **{f"ABACUS_BOOTSTRAP_{role.upper()}_PASSWORD": GOOD for role in db_bootstrap.ROLES},
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_every_app_role_gets_its_own_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    assert sorted(db_bootstrap.passwords()) == [
        "abacus_app",
        "abacus_identity",
        "abacus_ops",
        "abacus_owner",
        "abacus_relay",
    ]


def test_a_missing_or_short_password_is_named_never_echoed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    monkeypatch.setenv("ABACUS_BOOTSTRAP_RELAY_PASSWORD", SHORT)
    with pytest.raises(db_bootstrap.BootstrapError) as raised:
        db_bootstrap.passwords()
    assert "ABACUS_BOOTSTRAP_RELAY_PASSWORD" in str(raised.value)
    assert SHORT not in str(raised.value)
    monkeypatch.delenv("ABACUS_BOOTSTRAP_OPS_PASSWORD")
    monkeypatch.setenv("ABACUS_BOOTSTRAP_RELAY_PASSWORD", GOOD)
    with pytest.raises(db_bootstrap.BootstrapError, match="ABACUS_BOOTSTRAP_OPS_PASSWORD"):
        db_bootstrap.passwords()


def test_the_admin_dsn_quotes_the_master_password_and_verifies_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    dsn = db_bootstrap.admin_dsn()
    assert "p%40ss%2Fword%3Fwith%26chars" in dsn
    assert dsn.endswith("sslmode=verify-full")


def test_the_sql_it_applies_is_the_bootstrap_file() -> None:
    assert db_bootstrap.SQL.name == "bootstrap.sql"
    assert db_bootstrap.SQL.exists()


def test_main_reports_a_missing_input_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _env(monkeypatch)
    monkeypatch.delenv("ABACUS_DB_HOST")
    assert db_bootstrap.main() == 2
    assert "ABACUS_DB_HOST" in capsys.readouterr().err


def test_a_stored_large_object_fails_the_guard() -> None:
    with pytest.raises(db_bootstrap.BootstrapError, match="ED-292"):
        db_bootstrap._judge(1, 0)  # pyright: ignore[reportPrivateUsage] -- the guard's verdict


def test_open_functions_alone_are_reported_not_fatal(capsys: pytest.CaptureFixture[str]) -> None:
    db_bootstrap._judge(0, 7)  # pyright: ignore[reportPrivateUsage] -- the guard's verdict
    assert "7 large-object functions" in capsys.readouterr().err
