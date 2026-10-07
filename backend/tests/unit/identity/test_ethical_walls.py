"""AC-4, AC-7, AC-8, AC-11, AC-20: ethical walls in `authorise` and `visible` (TASK-016 interface
contract, "Enforcement"), with the database reads faked.

The matrix-driven cases are generated from `docs/architecture/permission-matrix.yaml`
(ADR-027): every human role is denied at layer `wall` on a walled client's engagement, for every
action, before relationship, role and attribute checks.
"""

from __future__ import annotations

import importlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast, get_args

import pytest
import yaml
from sqlalchemy import Uuid, column

import abacus.modules.engagements.api as engagements_api
import abacus.modules.identity.api as identity_api
from abacus.kernel.db import TenantContext
from abacus.modules.engagements.service import client_of, client_subquery
from abacus.modules.identity import authz
from abacus.modules.identity.api import (
    WALL_SAFE,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    register_engagement_client,
    visible,
)
from abacus.modules.identity.context import SystemContext, system_context_for_run
from abacus_tools.codegen import permission_matrix as pm

FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
FIRM_ROLES: tuple[FirmRole, ...] = get_args(FirmRole)
ENGAGEMENT_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer")
HUMAN_ROLES = (*FIRM_ROLES, *ENGAGEMENT_ROLES)
ACTIONS = cast(
    dict[str, dict[str, str]],
    cast(dict[str, object], yaml.safe_load(pm.SOURCE.read_text()))["actions"],
)
REASON = "documented in the working paper"
WALL_SQL = "NOT (EXISTS (SELECT ethical_walls.id FROM ethical_walls WHERE "
PAIRS = [(a, r) for a in ACTIONS for r in HUMAN_ROLES]
IDS = [f"{a}-{r}" for a, r in PAIRS]
ALLOWED = [
    (a, r) for a, r in PAIRS if ACTIONS[a].get(r) == "allow" and ACTIONS[a].get("notify") is None
]
ALLOWED_IDS = [f"{a}-{r}" for a, r in ALLOWED]


class Fakes:
    """Stands in for the reads of `engagement_members`, `ethical_walls` and the engagement's
    client; records its calls."""

    def __init__(self) -> None:
        self.role: str | None = None
        self.walls: dict[uuid.UUID, frozenset[uuid.UUID]] = {}
        self.clients: dict[uuid.UUID, uuid.UUID | None] = {}
        self.wall_calls: list[uuid.UUID] = []
        self.lookups: list[tuple[TenantContext, uuid.UUID]] = []

    async def engagement_role(
        self, tenant: TenantContext, user_id: uuid.UUID, engagement_id: uuid.UUID
    ) -> str | None:
        return self.role

    async def walled(self, tenant: TenantContext, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
        self.wall_calls.append(user_id)
        return self.walls.get(user_id, frozenset())

    async def lookup(self, tenant: TenantContext, engagement_id: uuid.UUID) -> uuid.UUID | None:
        self.lookups.append((tenant, engagement_id))
        return self.clients.get(engagement_id)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    made = Fakes()
    monkeypatch.setattr(authz, "engagement_role", made.engagement_role)
    monkeypatch.setattr(authz, "walled_clients", made.walled)
    # Start unregistered (restored after the test), then register the fake lookup.
    monkeypatch.setattr(authz, "_engagement_client", None)
    register_engagement_client(client_subquery, made.lookup)
    return made


def _ctx(
    firm_role: FirmRole | None = None, mfa_ago: timedelta | None = timedelta(minutes=1)
) -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,
        mfa_at=None if mfa_ago is None else datetime.now(UTC) - mfa_ago,
    )


def _on(ctx: AuthContext, client: uuid.UUID | None, *, archived: bool = False) -> Resource:
    return Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=archived, client_id=client)


async def _layer(ctx: AuthContext | SystemContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource, reason=REASON)
    return raised.value.layer


def _arranged(role: str, fakes: Fakes) -> AuthContext:
    if role in FIRM_ROLES:
        return _ctx(role)
    fakes.role = role
    return _ctx()


# --- AC-4: every role, every engagement-scoped action ----------------------------------------


@pytest.mark.parametrize(("action", "role"), PAIRS, ids=IDS)
async def test_ac4_a_walled_person_is_denied_at_layer_wall_whatever_their_role(
    fakes: Fakes, action: str, role: str
) -> None:
    ctx = _arranged(role, fakes)
    client = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({client})
    assert await _layer(ctx, action, _on(ctx, client)) == "wall"


@pytest.mark.parametrize(("action", "role"), ALLOWED, ids=ALLOWED_IDS)
async def test_ac8_the_same_person_is_allowed_on_another_client_where_the_matrix_allows(
    fakes: Fakes, action: str, role: str
) -> None:
    ctx = _arranged(role, fakes)
    fakes.walls[ctx.user_id] = frozenset({uuid.uuid4()})
    await authorise(ctx, action, _on(ctx, uuid.uuid4()), reason=REASON)


async def test_ac4_the_wall_is_checked_before_relationship(fakes: Fakes) -> None:
    ctx = _ctx()  # no firm role and no engagement role: relationship would deny
    client = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({client})
    assert await _layer(ctx, "engagement.read", _on(ctx, client)) == "wall"


async def test_ac4_the_wall_is_checked_before_role_and_attribute(fakes: Fakes) -> None:
    ctx = _arranged("reviewer", fakes)
    client = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({client})
    # a role denial and an archived write would both deny; the wall comes first
    assert await _layer(ctx, "request_item.waive", _on(ctx, client, archived=True)) == "wall"


async def test_ac4_tenancy_is_still_checked_before_the_wall(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    client = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({client})
    other = Resource.engagement(uuid.uuid4(), uuid.uuid4(), archived=False, client_id=client)
    assert await _layer(ctx, "engagement.read_metadata", other) == "tenancy"


async def test_ac4_firm_level_resources_are_never_walled(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    fakes.walls[ctx.user_id] = frozenset({uuid.uuid4()})
    await authorise(ctx, "wall.create", Resource.firm(ctx.tenant_id))
    await authorise(ctx, "engagement.create", Resource.firm(ctx.tenant_id))


async def test_ac4_several_walls_apply_as_a_union(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    first, second, free = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({first, second})
    assert await _layer(ctx, "engagement.read_metadata", _on(ctx, first)) == "wall"
    assert await _layer(ctx, "engagement.read_metadata", _on(ctx, second)) == "wall"
    await authorise(ctx, "engagement.read_metadata", _on(ctx, free))


async def test_ac4_someone_elses_wall_does_not_apply(fakes: Fakes) -> None:
    ctx, other, client = _ctx("firm_admin"), uuid.uuid4(), uuid.uuid4()
    fakes.walls[other] = frozenset({client})
    await authorise(ctx, "engagement.read_metadata", _on(ctx, client))


def test_ac4_forbidden_at_layer_wall_carries_its_layer() -> None:
    assert Forbidden("engagement.read", "wall").layer == "wall"


# --- where the client comes from -------------------------------------------------------------


async def test_ac4_resource_client_id_is_used_when_set_and_the_lookup_is_not_asked(
    fakes: Fakes,
) -> None:
    ctx = _ctx("firm_admin")
    walled, free = uuid.uuid4(), uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({walled})
    resource = _on(ctx, free)
    assert resource.engagement_id is not None
    fakes.clients[resource.engagement_id] = walled  # would deny, if it were asked
    await authorise(ctx, "engagement.read_metadata", resource)
    assert fakes.lookups == []


async def test_ac4_without_a_client_id_the_registered_lookup_decides(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    walled = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({walled})
    resource = _on(ctx, None)
    assert resource.engagement_id is not None
    fakes.clients[resource.engagement_id] = walled
    assert await _layer(ctx, "engagement.read_metadata", resource) == "wall"
    assert fakes.lookups == [(ctx.tenant, resource.engagement_id)]
    fakes.clients[resource.engagement_id] = uuid.uuid4()
    await authorise(ctx, "engagement.read_metadata", resource)


async def test_ac4_unregistered_a_walled_person_without_a_client_id_is_denied(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_engagement_client", None)
    ctx = _ctx("firm_admin")
    fakes.walls[ctx.user_id] = frozenset({uuid.uuid4()})
    assert await _layer(ctx, "engagement.read_metadata", _on(ctx, None)) == "wall"


async def test_ac8_unregistered_a_person_with_no_walls_is_unaffected(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_engagement_client", None)
    ctx = _ctx("firm_admin")
    await authorise(ctx, "engagement.read_metadata", _on(ctx, None))


async def test_ac4_unregistered_a_client_id_on_the_resource_still_decides(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_engagement_client", None)
    ctx = _ctx("firm_admin")
    walled = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({walled})
    assert await _layer(ctx, "engagement.read_metadata", _on(ctx, walled)) == "wall"
    await authorise(ctx, "engagement.read_metadata", _on(ctx, uuid.uuid4()))


# --- system contexts (AC-7) -------------------------------------------------------------------


def _system(on_behalf_of: uuid.UUID) -> SystemContext:
    return system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        on_behalf_of=on_behalf_of,
    )


SYSTEM_ACTIONS = [
    a
    for a, e in ACTIONS.items()
    if e.get("system") == "allow" and not any(k in e for k in ("mfa_recent", "requires", "notify"))
]


def _system_resource(ctx: SystemContext, client: uuid.UUID) -> Resource:
    return Resource.engagement(ctx.tenant_id, ctx.engagement_id, archived=False, client_id=client)


@pytest.mark.parametrize("action", SYSTEM_ACTIONS)
async def test_ac7_a_system_run_is_denied_when_the_person_it_acts_for_is_walled(
    fakes: Fakes, action: str
) -> None:
    person, client = uuid.uuid4(), uuid.uuid4()
    ctx = _system(person)
    fakes.walls[person] = frozenset({client})
    assert await _layer(ctx, action, _system_resource(ctx, client)) == "wall"
    assert fakes.wall_calls == [person]  # it is the person, not the run, that is asked about


@pytest.mark.parametrize("action", SYSTEM_ACTIONS)
async def test_ac8_a_system_run_for_a_person_walled_from_another_client_is_unaffected(
    fakes: Fakes, action: str
) -> None:
    person = uuid.uuid4()
    ctx = _system(person)
    fakes.walls[person] = frozenset({uuid.uuid4()})
    await authorise(ctx, action, _system_resource(ctx, uuid.uuid4()))


async def test_ac7_a_system_run_is_unaffected_by_someone_elses_wall(fakes: Fakes) -> None:
    person, client = uuid.uuid4(), uuid.uuid4()
    ctx = _system(person)
    fakes.walls[uuid.uuid4()] = frozenset({client})
    await authorise(ctx, SYSTEM_ACTIONS[0], _system_resource(ctx, client))


async def test_ac7_outside_a_request_walls_are_read_live_on_every_authorise(
    fakes: Fakes,
) -> None:
    person, client = uuid.uuid4(), uuid.uuid4()
    ctx = _system(person)
    resource = _system_resource(ctx, client)
    await authorise(ctx, SYSTEM_ACTIONS[0], resource)
    fakes.walls[person] = frozenset({client})  # walled between two steps of the run
    assert await _layer(ctx, SYSTEM_ACTIONS[0], resource) == "wall"
    assert fakes.wall_calls == [person, person]


async def test_ac20_inside_a_request_walls_are_read_once_per_person(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    fakes.walls[ctx.user_id] = frozenset()
    with authz.recording_checks():
        await authorise(ctx, "engagement.read_metadata", _on(ctx, uuid.uuid4()))
        await authorise(ctx, "engagement.read_metadata", _on(ctx, uuid.uuid4()))
    assert fakes.wall_calls == [ctx.user_id]
    with authz.recording_checks():  # a new request reads again
        await authorise(ctx, "engagement.read_metadata", _on(ctx, uuid.uuid4()))
    assert fakes.wall_calls == [ctx.user_id, ctx.user_id]


async def test_ac20_a_wall_denial_is_logged_with_layer_wall_and_ids_only(
    fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _ctx("firm_admin")
    client = uuid.uuid4()
    fakes.walls[ctx.user_id] = frozenset({client})
    capsys.readouterr()
    assert await _layer(ctx, "engagement.read_metadata", _on(ctx, client)) == "wall"
    captured = capsys.readouterr()
    lines = [line for line in (captured.out + captured.err).splitlines() if line.startswith("{")]
    [event] = [e for e in map(json.loads, lines) if e["event"] == "authz.denied"]
    assert event["layer"] == "wall"
    assert event["action"] == "engagement.read_metadata"
    assert event["tenant_id"] == str(ctx.tenant_id)
    assert event["user_id"] == str(ctx.user_id)


# --- visible ----------------------------------------------------------------------------------


def _sql(expression: object) -> str:
    return " ".join(str(expression).split())


def test_ac5_visible_adds_the_wall_filter_for_the_acting_person_and_tenant(fakes: Fakes) -> None:
    ctx = _ctx("firm_admin")
    expression = visible(ctx, "engagement.read_metadata", column("engagement_id", Uuid()))
    assert WALL_SQL in _sql(expression)
    params = expression.compile().params
    assert ctx.user_id in params.values()
    assert ctx.tenant_id in params.values()
    assert "active" in params.values()


def test_ac7_visible_for_a_system_context_filters_by_the_person_it_acts_for(fakes: Fakes) -> None:
    person = uuid.uuid4()
    ctx = _system(person)
    expression = visible(ctx, "evidence.read", column("engagement_id", Uuid()))
    if ACTIONS["evidence.read"].get("system") == "allow":
        assert person in expression.compile().params.values()
    else:
        assert _sql(expression) == "false"


def test_ac5_visible_correlates_the_client_with_the_engagement_id_column(fakes: Fakes) -> None:
    expression = visible(
        _ctx("firm_admin"), "engagement.read_metadata", column("engagement_id", Uuid())
    )
    assert "ethical_walls.client_id = (SELECT" in _sql(expression)
    assert "FROM engagements" in _sql(expression)


def test_ac20_importing_the_engagements_api_registers_the_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authz, "_engagement_client", None)
    bare = _sql(visible(_ctx("firm_admin"), "engagement.read_metadata", column("e", Uuid())))
    assert "FROM engagements" not in bare
    importlib.reload(engagements_api)
    registered = _sql(visible(_ctx("firm_admin"), "engagement.read_metadata", column("e", Uuid())))
    assert "FROM engagements" in registered


def test_ac20_registering_the_same_pair_twice_is_a_no_op(fakes: Fakes) -> None:
    register_engagement_client(client_subquery, fakes.lookup)
    register_engagement_client(client_subquery, fakes.lookup)


def test_ac20_registering_a_different_pair_raises(fakes: Fakes) -> None:
    async def other(tenant: TenantContext, engagement_id: uuid.UUID) -> uuid.UUID | None:
        return None

    with pytest.raises(RuntimeError):
        register_engagement_client(client_subquery, other)
    with pytest.raises(RuntimeError):
        register_engagement_client(client_subquery, client_of)


def test_ac20_registration_is_part_of_the_identity_api() -> None:
    assert "register_engagement_client" in identity_api.__all__


# --- AC-11 ------------------------------------------------------------------------------------


def test_ac11_wall_safe_is_true() -> None:
    assert WALL_SAFE is True
    assert identity_api.WALL_SAFE is True
