"""SPEC-025 AC-7 (per person; TASK-045): a staff engagement role grants a client-data action only
once that person has confirmed their independence for the engagement.

The engagement role, walls and the engagements module's confirmation lookup are replaced by
fakes; `authz._independence` is set directly, as `register_independence` would.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import yaml
from sqlalchemy import ColumnElement, Uuid, column, literal_column

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
    visible,
)
from abacus.modules.identity.authz import recording_checks
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import permission_matrix as pm

DOCUMENT = cast(dict[str, object], yaml.safe_load(pm.SOURCE.read_text()))
ACTIONS = cast(dict[str, dict[str, str]], DOCUMENT["actions"])
STAFF_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer")
MARKED = sorted(a for a, entries in ACTIONS.items() if entries.get("independence") == "required")
MARKED_STAFF = [(a, r) for a in MARKED for r in STAFF_ROLES if ACTIONS[a].get(r) == "allow"]
MARKED_STAFF_IDS = [f"{a}-{r}" for a, r in MARKED_STAFF]


class Fakes:
    def __init__(self) -> None:
        self.role: str | None = "staff"
        self.confirmed = False
        self.lookups: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def engagement_role(self, *args: object) -> str | None:
        return self.role

    async def walled(self, *args: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def confirmed_for(
        self, tenant: TenantContext, engagement_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        self.lookups.append((engagement_id, user_id))
        return self.confirmed


def _confirmed_column(engagement_id: object, user_id: uuid.UUID) -> ColumnElement[bool]:
    return literal_column("independence_confirmed")


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    made = Fakes()
    monkeypatch.setattr(authz, "engagement_role", made.engagement_role)
    monkeypatch.setattr(authz, "walled_clients", made.walled)
    monkeypatch.setattr(authz, "_independence", (_confirmed_column, made.confirmed_for))
    return made


def _person(*, support: str | None = None) -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), "support" if support else "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role=support,  # pyright: ignore[reportArgumentType] -- a support role under test
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _on(ctx: AuthContext | AgentContext, engagement_id: uuid.UUID | None = None) -> Resource:
    return Resource.engagement(ctx.tenant_id, engagement_id or uuid.uuid4(), archived=False)


def _agent(initiator: AuthContext, engagement_id: uuid.UUID) -> AgentContext:
    run_id = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(initiator.tenant_id, "agent", f"agent:engagement.agent:{run_id}"),
        agent_id="engagement.agent",
        agent_run_id=run_id,
        engagement_id=engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


async def _layer(ctx: AuthContext | AgentContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource)
    return raised.value.layer


def _sql(expression: ColumnElement[bool]) -> str:
    return " ".join(str(expression.compile()).split())


def test_ac7_the_client_data_actions_are_marked() -> None:
    assert MARKED == [
        "connection.read_log",
        "evidence.accept",
        "evidence.read",
        "evidence.reject",
        "evidence.upload",
        "review.assign",
        "review.read",
        "review.take",
        "screening.request",
    ]
    assert all(RULES[a].independence for a in MARKED)
    assert not RULES["request_item.read"].independence


@pytest.mark.parametrize(("action", "role"), MARKED_STAFF, ids=MARKED_STAFF_IDS)
async def test_ac7_a_confirmed_staff_member_is_allowed(
    fakes: Fakes, action: str, role: str
) -> None:
    fakes.role, fakes.confirmed = role, True
    ctx = _person()
    await authorise(ctx, action, _on(ctx))


@pytest.mark.parametrize(("action", "role"), MARKED_STAFF, ids=MARKED_STAFF_IDS)
async def test_ac7_an_unconfirmed_staff_member_is_refused_at_independence(
    fakes: Fakes, action: str, role: str
) -> None:
    fakes.role = role  # requested or declined: anything but confirmed
    ctx = _person()
    engagement_id = uuid.uuid4()
    assert await _layer(ctx, action, _on(ctx, engagement_id)) == "independence"
    assert fakes.lookups == [(engagement_id, ctx.user_id)]


async def test_ac7_an_unconfirmed_member_still_sees_what_is_asked(fakes: Fakes) -> None:
    ctx = _person()
    await authorise(ctx, "request_item.read", _on(ctx))
    assert fakes.lookups == []


@pytest.mark.parametrize(
    ("action", "role"),
    [("evidence.upload", "client_admin"), ("connection.read_log", "client_admin")],
)
async def test_ac7_client_roles_are_not_bound_by_the_firms_independence(
    fakes: Fakes, action: str, role: str
) -> None:
    fakes.role = role
    ctx = _person()
    await authorise(ctx, action, _on(ctx))
    assert fakes.lookups == []


async def test_ac7_break_glass_support_is_not_bound(fakes: Fakes) -> None:
    fakes.role = None
    ctx = _person(support="platform_support_content")
    await authorise(ctx, "evidence.read", _on(ctx))
    assert fakes.lookups == []


async def test_ac7_a_system_run_is_not_bound(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    ctx = system_context_for_run(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        engagement_id=engagement_id,
        on_behalf_of=uuid.uuid4(),
    )
    await authorise(
        ctx, "evidence.upload", Resource.engagement(ctx.tenant_id, engagement_id, archived=False)
    )
    assert fakes.lookups == []


async def test_ac7_an_agent_of_an_unconfirmed_person_is_refused(fakes: Fakes) -> None:
    engagement_id = uuid.uuid4()
    agent = _agent(_person(), engagement_id)
    assert await _layer(agent, "evidence.read", _on(agent, engagement_id)) == "delegation"
    fakes.confirmed = True
    await authorise(agent, "evidence.read", _on(agent, engagement_id))


async def test_ac7_unregistered_means_refused(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    fakes.confirmed = True
    ctx = _person()
    assert await _layer(ctx, "evidence.read", _on(ctx)) == "independence"


async def test_ac7_the_answer_is_read_once_per_request(fakes: Fakes) -> None:
    fakes.confirmed = True
    ctx = _person()
    resource = _on(ctx)
    with recording_checks():
        await authorise(ctx, "evidence.read", resource)
        await authorise(ctx, "review.read", resource)
    assert len(fakes.lookups) == 1


async def test_ac7_confirming_on_one_engagement_does_not_open_another(fakes: Fakes) -> None:
    ctx = _person()
    confirmed_on = uuid.uuid4()

    async def only_one(tenant: object, engagement_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return engagement_id == confirmed_on

    authz._independence = (_confirmed_column, only_one)  # pyright: ignore[reportPrivateUsage] -- restored by the fixture's monkeypatch
    await authorise(ctx, "evidence.read", _on(ctx, confirmed_on))
    assert await _layer(ctx, "evidence.read", _on(ctx)) == "independence"


# --- visible ---------------------------------------------------------------------------------


def test_ac7_visible_requires_a_confirmation_for_staff_roles(fakes: Fakes) -> None:
    sql = _sql(visible(_person(), "connection.read_log", column("engagement_id", Uuid())))
    assert "independence_confirmed" in sql
    # Staff roles need the confirmation; client roles reach their rows without one.
    assert sql.count("engagement_members.role IN") == 2
    assert sql.startswith("(engagement_id IN (SELECT engagement_members.engagement_id")
    assert " OR engagement_id IN (SELECT" in sql
    assert sql.index("independence_confirmed") > sql.index(" OR ")


def test_ac7_visible_unregistered_leaves_only_client_reach(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    expression = visible(_person(), "connection.read_log", column("engagement_id", Uuid()))
    assert "independence_confirmed" not in _sql(expression)
    assert _sql(expression).count("engagement_members.role IN") == 1
    assert expression.compile().params["role_1"] == ["client_admin"]


def test_ac7_visible_with_only_staff_roles_unregistered_is_false(
    fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(authz, "_independence", None)
    sql = _sql(visible(_person(), "review.read", column("engagement_id", Uuid())))
    assert sql.startswith("false")


def test_ac7_visible_for_an_unmarked_read_is_unchanged(fakes: Fakes) -> None:
    sql = _sql(visible(_person(), "request_item.read", column("engagement_id", Uuid())))
    assert "independence_confirmed" not in sql
