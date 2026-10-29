"""A-02-T33: the live ledger's host and redirect are fixed at boot.

Production refuses fake providers at boot (the fake connector already: `fake_connector_dir` is
local and test only) and now QuickBooks Online's sandbox host, and needs the one registered
redirect host on the neutral portal domain; staging and local refuse Intuit's live host, so a test
environment never reads a firm's real books. Unregistered (no `qbo_client_id`), nothing is checked:
the connector stays dark.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from abacus.kernel.config import Settings

from .test_config import (
    _explicit_connection_env,  # pyright: ignore[reportPrivateUsage] -- the suite's full set of required settings
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


def _env(monkeypatch: pytest.MonkeyPatch, environment: str, **values: str) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    if environment in ("staging", "production"):
        _explicit_connection_env(monkeypatch)
    for name, value in values.items():
        monkeypatch.setenv(f"ABACUS_{name.upper()}", value)


def test_production_refuses_the_sandbox_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(
        monkeypatch,
        "production",
        qbo_client_id="app",
        connections_redirect_base_url="https://c.example.test",
    )
    with pytest.raises(ValueError, match="refuses qbo_environment 'sandbox'"):
        Settings()


def test_production_needs_the_registered_redirect_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, "production", qbo_client_id="app", qbo_environment="production")
    with pytest.raises(ValueError, match="connections_redirect_base_url"):
        Settings()


def test_production_with_the_live_host_and_the_redirect_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(
        monkeypatch,
        "production",
        qbo_client_id="app",
        qbo_environment="production",
        connections_redirect_base_url="https://connect.example.test",
    )
    settings = Settings()
    assert settings.qbo_environment == "production"


@pytest.mark.parametrize("environment", ["local", "test", "staging"])
def test_other_environments_refuse_the_live_host(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _env(monkeypatch, environment, qbo_client_id="app", qbo_environment="production")
    with pytest.raises(ValueError, match="refuses qbo_environment 'production'"):
        Settings()


def test_an_unregistered_connector_is_not_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, "production")
    assert Settings().qbo_client_id is None


def test_production_still_refuses_the_fake_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, "production", fake_connector_dir="fixtures/fake")
    with pytest.raises(ValueError, match="fake_connector_dir"):
        Settings()


def test_the_callback_uses_the_registered_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.kernel.config import settings
    from abacus.modules.connections import connect

    monkeypatch.setenv("ABACUS_CONNECTIONS_REDIRECT_BASE_URL", "https://connect.example.test")
    settings.cache_clear()
    try:
        assert connect.redirect_uri().startswith("https://connect.example.test/")
    finally:
        settings.cache_clear()
