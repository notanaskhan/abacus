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


# --- DEC-1012: on staging each firm gets its tenant key before anything is sealed ---------------


class _Handle:
    def __init__(self, result: object) -> None:
        self._result = result

    async def result(self) -> object:
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


def _temporal(mp: pytest.MonkeyPatch, result: object, asked: list[str]) -> None:
    class Client:
        def get_workflow_handle(self, workflow_id: str) -> _Handle:
            asked.append(workflow_id)
            return _Handle(result)

    async def client() -> Client:
        return Client()

    mp.setattr(loader, "temporal_client", client)


async def test_ensure_tenant_key_starts_the_firms_key_workflow_and_returns_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[tuple[type, object, dict[str, object]]] = []

    async def dispatch(workflow: type, arg: object, **options: object) -> None:
        started.append((workflow, arg, options))

    asked: list[str] = []
    monkeypatch.setattr(loader, "dispatch", dispatch)
    _temporal(monkeypatch, "verified arn:replica", asked)
    assert await loader.ensure_tenant_key(loader.TENANT) == "verified arn:replica"
    [(workflow, arg, options)] = started
    assert workflow is loader.TenantKeyWorkflow
    assert arg == loader.TenantKeyInput(str(loader.TENANT), loader.LOADER)
    assert options["id"] == loader.tenant_key_workflow_id(str(loader.TENANT))
    assert options["id_reuse_policy"] == loader.WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    assert asked == [options["id"]]


async def test_a_key_workflow_that_already_completed_is_read_not_started_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def dispatch(_workflow: type, _arg: object, **options: object) -> None:
        raise loader.WorkflowAlreadyStartedError(str(options["id"]), "TenantKey")

    asked: list[str] = []
    monkeypatch.setattr(loader, "dispatch", dispatch)
    _temporal(monkeypatch, "verified", asked)
    assert await loader.ensure_tenant_key(loader.SANDBOX) == "verified"
    assert asked == [loader.tenant_key_workflow_id(str(loader.SANDBOX))]


async def test_a_key_that_is_not_verified_in_time_refuses_the_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def dispatch(_workflow: type, _arg: object, **_options: object) -> None:
        return None

    monkeypatch.setattr(loader, "dispatch", dispatch)
    _temporal(monkeypatch, TimeoutError(), [])
    with pytest.raises(loader.KeyTimeout, match="not verified"):
        await loader.ensure_tenant_key(loader.TENANT, timeout=0.01)


@pytest.mark.parametrize(("staging", "keyed"), [(True, 1), (False, 0)])
async def test_a_staging_load_keys_the_firm_even_when_it_was_loaded_before(
    monkeypatch: pytest.MonkeyPatch, staging: bool, keyed: int
) -> None:
    """Today's failure: a firm bootstrapped by an earlier run, never keyed, then skipped."""
    firm = next(e for e in build("E0").events if e.kind == "identity.firm_created")
    keys: list[object] = []

    async def nothing(*_args: object, **_kwargs: object) -> None:
        return None

    async def loaded(_conn: object, _event: object) -> bool:
        return True

    async def synthetic(*_args: object) -> bool:
        return True

    async def key(tenant: object) -> str:
        keys.append(tenant)
        return "verified"

    class Conn:
        async def close(self) -> None:
            return None

    async def connect(_dsn: str) -> Conn:
        return Conn()

    def guard(_dsn: str, *, staging: bool) -> None:
        return None

    def scenario(*_args: object) -> SimpleNamespace:
        return SimpleNamespace(events=(firm,))

    monkeypatch.setattr(loader, "guard", guard)
    monkeypatch.setattr(loader, "build", scenario)
    monkeypatch.setattr(loader, "connect_db", connect)
    monkeypatch.setattr(loader, "tenant_value", synthetic)
    monkeypatch.setattr(loader, "preflight", nothing)
    monkeypatch.setattr(loader, "_already_loaded", loaded)
    monkeypatch.setattr(loader, "ensure_tenant_key", key)
    result = await loader.load(LOCAL, staging=staging)
    assert result == loader.LoadResult(0, 1)
    assert keys == [loader.TENANT] * keyed
