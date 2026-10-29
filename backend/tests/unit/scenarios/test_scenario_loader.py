"""F-04-T13 (F-04.15, F-04.16): the loader's guards, trace ids and replay order, without a
database. The load itself is covered by tests/integration/test_scenario_loader.py."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

LOCAL = "postgresql://postgres:postgres@127.0.0.1:55432/abacus"


def _environment(
    mp: pytest.MonkeyPatch, environment: str, hosted: list[str] | None = None
) -> None:
    mp.setattr(loader, "settings", lambda: SimpleNamespace(environment=environment))
    mp.setattr(loader, "violations", lambda: hosted or [])


def test_production_is_refused_in_every_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "production")
    for staging in (False, True):
        with pytest.raises(loader.LoadRefused, match="production"):
            loader.guard(LOCAL, staging=staging)


@pytest.mark.parametrize(
    "dsn", ["postgresql://u:p@db.example.test:5432/abacus", "postgresql://u:p@10.0.0.4/abacus"]
)
def test_a_laptop_load_refuses_a_non_loopback_dsn(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    _environment(monkeypatch, "local")
    with pytest.raises(loader.LoadRefused, match="this machine"):
        loader.guard(dsn, staging=False)


def test_a_laptop_load_refuses_when_any_configured_url_is_hosted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(monkeypatch, "local", ["ABACUS_DATABASE_URL"])
    with pytest.raises(loader.LoadRefused):
        loader.guard(LOCAL, staging=False)


def test_a_loopback_load_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "local")
    loader.guard(LOCAL, staging=False)


def test_staging_mode_needs_the_staging_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "local")
    with pytest.raises(loader.LoadRefused, match="staging"):
        loader.guard(LOCAL, staging=True)


def test_staging_refuses_while_a_deploy_is_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    _environment(monkeypatch, "staging")
    monkeypatch.setattr(loader, "deploy_in_flight", lambda: "run 42 (deploy)")
    with pytest.raises(loader.LoadRefused, match="run 42"):
        loader.guard("postgresql://u:p@db.example.test/abacus", staging=True)


def _no_gh(_name: str) -> None:
    return None


def _free(_env: str) -> None:
    return None


def test_without_gh_the_staging_check_reads_the_ssm_deploy_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEC-1005: inside the staging VPC (no gh) the deploy lock decides."""
    monkeypatch.setattr(loader.shutil, "which", _no_gh)
    monkeypatch.setattr(loader.deploy_lock, "held", _free)
    assert loader.deploy_in_flight() is None
    held = loader.deploy_lock.Lock(
        "deploy-staging", "run/7", "abc", "2026-10-29T10:00:00+00:00", "deploy"
    )

    def lock_held(_env: str) -> object:
        return held

    monkeypatch.setattr(loader.deploy_lock, "held", lock_held)
    assert loader.deploy_in_flight() == "deploy lock held by deploy-staging (run/7)"


def test_without_gh_or_ssm_the_staging_check_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_ssm(_env: str) -> None:
        raise RuntimeError("no credentials")

    monkeypatch.setattr(loader.shutil, "which", _no_gh)
    monkeypatch.setattr(loader.deploy_lock, "held", no_ssm)
    with pytest.raises(loader.LoadRefused, match="in flight"):
        loader.deploy_in_flight()


def test_each_event_has_a_stable_32_hex_trace() -> None:
    events = build("E0").events
    traces = [loader.trace_hex(e) for e in events]
    assert all(re.fullmatch(r"[0-9a-f]{32}", t) for t in traces)
    assert len(set(traces)) == len(traces)
    assert traces == [loader.trace_hex(e) for e in build("E0").events]


def test_replay_puts_the_firm_offices_and_people_before_clients() -> None:
    kinds = [e.kind for e in loader.replay_order(build("E0").events)]
    first_client = kinds.index("organisations.client_created")
    assert kinds[0] == "identity.firm_created"
    assert "identity.staff_member_added" not in kinds[first_client:]
    assert "organisations.office_created" not in kinds[first_client:]


def test_every_event_kind_has_a_handler() -> None:
    assert {e.kind for e in build("E0").events} <= set(loader.HANDLERS)
