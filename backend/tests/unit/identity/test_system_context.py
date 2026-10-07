"""AC-10, AC-20: `SystemContext`, `system_context`, and `authorise` / `visible` for the platform
actor (TASK-010a interface contract, "SystemContext").

Expectations are generated from `docs/architecture/permission-matrix.yaml`: the system holds the
role `system` and nothing else, so the matrix decides. The database read of engagement roles is
replaced as in the permission-matrix tests; for a system context it must never be consulted.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
import yaml
from sqlalchemy import Uuid, column

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.identity import api as identity_api
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    SystemContext,
    UnknownAction,
    authorise,
    system_context_for_run,
    visible,
)
from abacus.modules.identity.authz import matrix, recording_checks
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import permission_matrix as pm

make_rule = matrix._rule  # pyright: ignore[reportPrivateUsage] -- contract tests the validator

DOCUMENT = cast(dict[str, object], yaml.safe_load(Path(pm.SOURCE).read_text()))
YAML_ACTIONS = cast(dict[str, dict[str, str]], DOCUMENT["actions"])
READ_VERBS = {"read", "read_metadata", "read_log"}
CONTRACT_ALLOWED = {
    "connection.pull",
    "evidence.upload",
    "fulfilment.propose",
    "screening.run",
    "support_match.run",
}
REASON = "documented in the working paper"


def _is_read(action: str) -> bool:
    return action.split(".", 1)[1] in READ_VERBS


def _plain_allow(action: str) -> bool:
    entries = YAML_ACTIONS[action]
    return entries.get("system") == "allow" and not any(
        key in entries for key in ("mfa_recent", "requires", "notify")
    )


SYSTEM_ALLOWED = [a for a in YAML_ACTIONS if _plain_allow(a)]
SYSTEM_DENIED = [a for a in YAML_ACTIONS if YAML_ACTIONS[a].get("system") != "allow"]
READ_ACTIONS = [a for a in YAML_ACTIONS if _is_read(a)]


class EngagementRoles:
    """Stands in for the database read of `engagement_members`; records its calls."""

    def __init__(self) -> None:
        self.role: str | None = None
        self.walls: frozenset[uuid.UUID] = frozenset()  # TASK-016: nobody is walled by default
        self.calls: list[tuple[TenantContext, uuid.UUID, uuid.UUID]] = []

    async def __call__(
        self, tenant: TenantContext, user_id: uuid.UUID, engagement_id: uuid.UUID
    ) -> str | None:
        self.calls.append((tenant, user_id, engagement_id))
        return self.role

    async def walled(self, tenant: TenantContext, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
        return self.walls


@pytest.fixture
def engagement(monkeypatch: pytest.MonkeyPatch) -> EngagementRoles:
    fake = EngagementRoles()
    monkeypatch.setattr(authz, "engagement_role", fake)
    monkeypatch.setattr(authz, "walled_clients", fake.walled)
    return fake


def _human() -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _system(*, engagement_id: uuid.UUID | None = None) -> SystemContext:
    return system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=engagement_id or uuid.uuid4(),
        on_behalf_of=uuid.uuid4(),
    )


def _firm(ctx: SystemContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


def _own(ctx: SystemContext, *, archived: bool = False) -> Resource:
    return Resource.engagement(ctx.tenant_id, ctx.engagement_id, archived=archived)


def _other(ctx: SystemContext) -> Resource:
    return Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)


async def _denied(ctx: SystemContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource, reason=REASON)
    return raised.value.layer


# --- the builder and the context -------------------------------------------------------------


def test_ac20_system_context_for_run_builds_a_context_acting_as_its_run() -> None:
    tenant_id, run_id, engagement_id, user_id = (uuid.uuid4() for _ in range(4))
    ctx = system_context_for_run(
        tenant_id=tenant_id, run_id=run_id, engagement_id=engagement_id, on_behalf_of=user_id
    )
    assert isinstance(ctx, SystemContext)
    assert ctx.tenant == TenantContext(tenant_id, "system", f"run:{run_id}")
    assert ctx.tenant_id == tenant_id
    assert ctx.on_behalf_of == user_id
    assert ctx.run_id == run_id
    assert ctx.engagement_id == engagement_id


def test_ac20_the_builder_takes_keywords_only() -> None:
    with pytest.raises(TypeError):
        system_context_for_run(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())  # pyright: ignore[reportCallIssue] -- contract: keywords only


def test_ac20_each_run_has_its_own_actor_id() -> None:
    assert _system().tenant.actor_id != _system().tenant.actor_id
    assert _system().tenant.actor_kind == "system"


def test_ac20_constructing_a_system_context_directly_raises_type_error() -> None:
    run_id = uuid.uuid4()
    with pytest.raises(TypeError):
        SystemContext(  # pyright: ignore[reportCallIssue] -- the issuer token is the point
            TenantContext(uuid.uuid4(), "system", f"run:{run_id}"),
            uuid.uuid4(),
            run_id,
            uuid.uuid4(),
        )


@pytest.mark.parametrize("token", [None, object(), "issuer", 0])
def test_ac20_a_forged_issuer_token_raises_type_error(token: object) -> None:
    run_id = uuid.uuid4()
    with pytest.raises(TypeError):
        SystemContext(
            TenantContext(uuid.uuid4(), "system", f"run:{run_id}"),
            uuid.uuid4(),
            run_id,
            uuid.uuid4(),
            token,
        )


@pytest.mark.parametrize(
    "actor", [("human", "run:{run}"), ("system", "retrieval"), ("agent", "run:{run}")]
)
def test_ac20_a_system_context_must_act_as_its_own_run(actor: tuple[str, str]) -> None:
    run_id = uuid.uuid4()
    kind, actor_id = actor
    issuer = context._ISSUER  # pyright: ignore[reportPrivateUsage] -- proving the invariant
    with pytest.raises(ValueError):
        SystemContext(
            TenantContext(uuid.uuid4(), cast(ActorKind, kind), actor_id.format(run=run_id)),
            uuid.uuid4(),
            run_id,
            uuid.uuid4(),
            issuer,
        )


def test_ac20_a_system_context_for_another_run_id_is_refused() -> None:
    run_id = uuid.uuid4()
    issuer = context._ISSUER  # pyright: ignore[reportPrivateUsage] -- proving the invariant
    with pytest.raises(ValueError):
        SystemContext(
            TenantContext(uuid.uuid4(), "system", f"run:{uuid.uuid4()}"),
            uuid.uuid4(),
            run_id,
            uuid.uuid4(),
            issuer,
        )


def test_ac20_the_old_builder_is_gone() -> None:
    assert not hasattr(identity_api, "system_context")


def test_ac20_a_system_context_is_not_a_human_context() -> None:
    ctx = _system()
    assert not isinstance(ctx, AuthContext)
    assert not hasattr(ctx, "firm_role")
    assert not hasattr(ctx, "user_id")


def test_ac20_a_system_context_is_immutable() -> None:
    ctx = _system()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.engagement_id = uuid.uuid4()  # pyright: ignore[reportAttributeAccessIssue] -- frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.run_id = uuid.uuid4()  # pyright: ignore[reportAttributeAccessIssue] -- frozen


def test_ac20_the_issuer_token_is_not_shown_in_the_repr() -> None:
    assert "object object" not in repr(_system())


def test_ac20_the_contract_set_of_system_actions_is_what_the_matrix_grants_today() -> None:
    assert {
        a for a in YAML_ACTIONS if YAML_ACTIONS[a].get("system") == "allow"
    } == CONTRACT_ALLOWED
    assert set(SYSTEM_ALLOWED) == CONTRACT_ALLOWED


# --- authorise -------------------------------------------------------------------------------


@pytest.mark.parametrize("action", SYSTEM_ALLOWED)
async def test_ac20_the_system_may_do_what_the_matrix_allows_on_its_own_engagement(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    await authorise(ctx, action, _own(ctx), reason=REASON)
    assert engagement.calls == []  # a system has no engagement role to look up


@pytest.mark.parametrize("action", SYSTEM_ALLOWED)
async def test_ac20_the_system_has_no_relationship_to_another_engagement(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    assert await _denied(ctx, action, _other(ctx)) == "relationship"
    assert engagement.calls == []


@pytest.mark.parametrize("action", SYSTEM_ALLOWED)
async def test_ac20_the_system_has_no_relationship_to_a_firm_level_resource(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    assert await _denied(ctx, action, _firm(ctx)) == "relationship"


@pytest.mark.parametrize("action", SYSTEM_DENIED)
async def test_ac20_everything_else_is_forbidden_at_the_role_layer_on_its_engagement(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    assert await _denied(ctx, action, _own(ctx)) == "role"


@pytest.mark.parametrize("action", SYSTEM_DENIED)
async def test_ac20_everything_else_off_its_engagement_is_a_relationship_denial(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    assert await _denied(ctx, action, _other(ctx)) == "relationship"


async def test_ac20_a_system_allow_with_a_human_only_condition_is_not_a_grant(
    engagement: EngagementRoles, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, entries in {
        "probe_mfa.update": {"system": "allow", "mfa_recent": "required"},
        "probe_reason.update": {"system": "allow", "requires": "reason"},
        "probe_notify.update": {"system": "allow", "notify": "engagement_team"},
    }.items():
        monkeypatch.setitem(RULES, name, make_rule(name, entries))
    ctx = _system()
    assert await _denied(ctx, "probe_mfa.update", _own(ctx)) == "attribute"
    assert await _denied(ctx, "probe_notify.update", _own(ctx)) == "attribute"
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, "probe_reason.update", _own(ctx))
    assert raised.value.layer == "attribute"
    await authorise(ctx, "probe_reason.update", _own(ctx), reason=REASON)


@pytest.mark.parametrize("action", ["evidence.accept", "evidence.read", "engagement.create"])
async def test_ac20_the_system_never_picks_up_a_human_role(
    engagement: EngagementRoles, action: str
) -> None:
    engagement.role = "manager"  # the on_behalf_of user's role must not leak into the system
    ctx = _system()
    assert await _denied(ctx, action, _own(ctx)) == "role"
    assert engagement.calls == []


async def test_ac20_tenancy_is_checked_before_the_relationship() -> None:
    ctx = _system()
    other_firm = Resource.firm(uuid.uuid4())
    other_engagement = Resource.engagement(uuid.uuid4(), ctx.engagement_id, archived=False)
    for action in sorted(CONTRACT_ALLOWED):
        assert await _denied(ctx, action, other_firm) == "tenancy"
        assert await _denied(ctx, action, other_engagement) == "tenancy"


@pytest.mark.parametrize("action", ["evidence.upload", "fulfilment.propose", "connection.pull"])
async def test_ac20_an_archived_engagement_is_read_only_for_the_system_too(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _system()
    assert await _denied(ctx, action, _own(ctx, archived=True)) == "attribute"


async def test_ac20_a_successful_system_check_is_recorded_for_the_request(
    engagement: EngagementRoles,
) -> None:
    ctx = _system()
    with recording_checks() as checked:
        await authorise(ctx, "fulfilment.propose", _own(ctx))
    assert checked == {"fulfilment.propose"}


async def test_ac20_a_denied_system_check_is_not_recorded(engagement: EngagementRoles) -> None:
    ctx = _system()
    with recording_checks() as checked:
        await _denied(ctx, "evidence.accept", _own(ctx))
        await _denied(ctx, "evidence.upload", _other(ctx))
    assert checked == set()


async def test_ac20_an_unknown_action_is_an_unknown_action_for_the_system_too(
    engagement: EngagementRoles,
) -> None:
    ctx = _system()
    with pytest.raises(UnknownAction):
        await authorise(ctx, "no.such_action", _own(ctx))


async def test_ac20_a_human_staff_member_is_not_allowed_what_only_the_system_may_do(
    engagement: EngagementRoles,
) -> None:
    engagement.role = "staff"
    human = _human()
    resource = Resource.engagement(human.tenant_id, uuid.uuid4(), archived=False)
    with pytest.raises(Forbidden) as raised:
        await authorise(human, "connection.pull", resource)
    assert raised.value.layer == "role"


# --- decisions are logged --------------------------------------------------------------------


def _log_events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    lines = [line for line in (captured.out + captured.err).splitlines() if line.startswith("{")]
    return [json.loads(line) for line in lines]


async def test_ac20_an_allowed_system_decision_logs_the_run_and_the_human_it_acts_for(
    engagement: EngagementRoles, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _system()
    capsys.readouterr()
    await authorise(ctx, "evidence.upload", _own(ctx))
    [event] = [e for e in _log_events(capsys) if e["event"] == "authz.allowed"]
    assert event["action"] == "evidence.upload"
    assert event["tenant_id"] == str(ctx.tenant_id)
    assert event["system_run_id"] == str(ctx.run_id)
    assert event["on_behalf_of"] == str(ctx.on_behalf_of)
    assert "user_id" not in event


@pytest.mark.parametrize(
    ("layer", "action"),
    [("tenancy", "evidence.upload"), ("role", "evidence.accept")],
)
async def test_ac20_a_denied_system_decision_logs_the_run_the_human_and_the_layer(
    engagement: EngagementRoles, capsys: pytest.CaptureFixture[str], layer: str, action: str
) -> None:
    ctx = _system()
    resource = Resource.firm(uuid.uuid4()) if layer == "tenancy" else _own(ctx)
    capsys.readouterr()
    assert await _denied(ctx, action, resource) == layer
    [event] = [e for e in _log_events(capsys) if e["event"] == "authz.denied"]
    assert event["action"] == action
    assert event["layer"] == layer
    assert event["system_run_id"] == str(ctx.run_id)
    assert event["on_behalf_of"] == str(ctx.on_behalf_of)
    assert "user_id" not in event


async def test_ac20_a_human_decision_still_logs_user_id_and_no_system_fields(
    engagement: EngagementRoles, capsys: pytest.CaptureFixture[str]
) -> None:
    engagement.role = "staff"
    human = _human()
    capsys.readouterr()
    await authorise(
        human,
        "evidence.upload",
        Resource.engagement(human.tenant_id, uuid.uuid4(), archived=False),
    )
    [event] = [e for e in _log_events(capsys) if e["event"] == "authz.allowed"]
    assert event["user_id"] == str(human.user_id)
    assert "system_run_id" not in event
    assert "on_behalf_of" not in event


# --- visible ---------------------------------------------------------------------------------


def _sql(expression: object) -> str:
    return " ".join(str(expression).split())


# The role filter is unchanged by TASK-016; walls (ADR-026) add this clause after it, for the
# person the system acts for.
WALL_CLAUSE = "AND NOT (EXISTS (SELECT ethical_walls.id FROM ethical_walls WHERE "


@pytest.mark.parametrize("action", READ_ACTIONS)
def test_ac20_visible_for_the_system_follows_the_matrix(action: str) -> None:
    ctx = _system()
    expression = visible(ctx, action, column("engagement_id", Uuid()))
    if YAML_ACTIONS[action].get("system") == "allow":
        assert _sql(expression).startswith("engagement_id = :engagement_id_1 " + WALL_CLAUSE)
    else:
        assert _sql(expression) == "false"


def test_ac20_visible_for_an_allowed_system_is_its_own_engagement_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(RULES, "probe.read", make_rule("probe.read", {"system": "allow"}))
    ctx = _system()
    expression = visible(ctx, "probe.read", column("engagement_id", Uuid()))
    assert _sql(expression).startswith("engagement_id = :engagement_id_1 " + WALL_CLAUSE)
    params = expression.compile().params
    assert params["engagement_id_1"] == ctx.engagement_id
    assert ctx.on_behalf_of in params.values()  # the wall clause is for the person it acts for


@pytest.mark.parametrize(
    "entries",
    [{"system": "deny", "manager": "allow"}, {"manager": "allow"}, {"agent": "task_scope"}],
    ids=["deny", "absent", "other-roles-only"],
)
def test_ac20_visible_is_false_when_the_matrix_does_not_allow_the_system(
    monkeypatch: pytest.MonkeyPatch, entries: dict[str, str]
) -> None:
    monkeypatch.setitem(RULES, "probe.read", make_rule("probe.read", entries))
    assert _sql(visible(_system(), "probe.read", column("engagement_id", Uuid()))) == "false"


async def test_ac20_visible_and_authorise_agree_for_the_system(
    monkeypatch: pytest.MonkeyPatch, engagement: EngagementRoles
) -> None:
    monkeypatch.setitem(RULES, "probe.read", make_rule("probe.read", {"system": "allow"}))
    monkeypatch.setitem(RULES, "probe_two.read", make_rule("probe_two.read", {"manager": "allow"}))
    ctx = _system()
    await authorise(ctx, "probe.read", _own(ctx))
    assert await _denied(ctx, "probe.read", _other(ctx)) == "relationship"
    assert "engagement_id = :engagement_id_1" in _sql(
        visible(ctx, "probe.read", column("engagement_id", Uuid()))
    )
    assert await _denied(ctx, "probe_two.read", _own(ctx)) == "role"
    assert _sql(visible(ctx, "probe_two.read", column("engagement_id", Uuid()))) == "false"


def test_ac20_visible_counts_as_the_check_for_the_system_too() -> None:
    with recording_checks() as checked:
        visible(_system(), "engagement.read", column("engagement_id", Uuid()))
    assert checked == {"engagement.read"}


def test_ac20_visible_rejects_a_non_read_action_for_the_system() -> None:
    with pytest.raises(ValueError):
        visible(_system(), "evidence.upload", column("engagement_id", Uuid()))


def test_ac20_visible_rejects_an_unknown_action_for_the_system() -> None:
    with pytest.raises(UnknownAction):
        visible(_system(), "no.such_action", column("engagement_id", Uuid()))
