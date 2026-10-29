"""Q-03-T064: `authorise_own` (G-01-T13, DEC-91; INV-1), the identity/authz survivors.

From the function's contract: a firm action a person takes on their own row, allowed for a live
signed-in person whose membership here is an active staff one, when the matrix allows the cell
their firm role takes (without one: their partner level, else the `staff` cell), narrowed by the
firm's overrides, with fresh MFA where the action asks, and the check recorded. Support, a client
user, an agent, the system, someone with no membership here or a client membership are refused at
the relationship layer; a cell the matrix or the firm refuses, or an action with conditions, at
the role layer; a stale or missing MFA at the attribute layer.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.identity import authz
from abacus.modules.identity.authz.matrix import Decision, Rule
from abacus.modules.identity.context import Actor, AuthContext
from abacus.modules.identity.repository import FirmPolicy, FirmRole, MemberFacts

ACTION = "q03t064.own_row"
NOW = datetime(2027, 4, 20, 15, 0, tzinfo=UTC)
TENANT = uuid.uuid4()


def _rule(**decisions: Decision) -> Rule:
    return Rule(
        action=ACTION,
        decisions=dict(decisions),
        mfa_recent=False,
        requires_reason=False,
        notify=False,
    )


class World:
    def __init__(self) -> None:
        self.member: MemberFacts | None = MemberFacts(
            level=None, offshore=False, service_lines=frozenset(), client=False
        )
        self.overrides: dict[tuple[str, str], str] = {}
        self.member_calls = 0


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    found = World()

    async def facts(*_: object) -> MemberFacts | None:
        found.member_calls += 1
        return found.member

    async def policy(*_: object) -> FirmPolicy:
        return FirmPolicy(overrides=dict(found.overrides), settings_on=frozenset())

    monkeypatch.setattr(authz, "member_facts", facts)
    monkeypatch.setattr(authz, "firm_policy", policy)
    monkeypatch.setattr(authz, "system_now", lambda: NOW)
    yield found


def _set_rule(monkeypatch: pytest.MonkeyPatch, rule: Rule) -> None:
    monkeypatch.setitem(authz.RULES, ACTION, rule)


def _person(
    firm_role: str | None = None,
    *,
    kind: str = "human",
    client: bool = False,
    mfa_at: datetime | None = NOW,
) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, cast(ActorKind, kind), str(user)),
        user,
        uuid.uuid4(),
        cast(FirmRole | None, firm_role),
        mfa_at,
        client=client,
    )


async def _layer(ctx: object) -> str:
    with pytest.raises(authz.Forbidden) as refused:
        await authz.authorise_own(cast(Actor, ctx), ACTION)
    return refused.value.layer


async def test_a_staff_member_with_their_cell_is_allowed_and_the_check_recorded(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, _rule(staff="allow"))
    with authz.recording_checks() as checked:
        await authz.authorise_own(_person(), ACTION)
    assert checked == {ACTION}
    assert world.member_calls == 1


@pytest.mark.parametrize(
    "ctx",
    [
        pytest.param(lambda: _person(kind="system"), id="system"),
        pytest.param(lambda: _person(kind="agent"), id="agent-actor"),
        pytest.param(lambda: _person(client=True), id="client-user"),
        pytest.param(lambda: _person(kind="support"), id="support"),
    ],
)
async def test_anyone_but_a_live_person_is_refused_at_the_relationship(
    monkeypatch: pytest.MonkeyPatch, world: World, ctx: Callable[[], AuthContext]
) -> None:
    _set_rule(monkeypatch, _rule(staff="allow", firm_admin="allow"))
    assert await _layer(ctx()) == "relationship"
    assert world.member_calls == 0  # refused before any membership read


async def test_no_membership_here_or_a_client_membership_is_refused_at_the_relationship(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, _rule(staff="allow"))
    world.member = None
    assert await _layer(_person()) == "relationship"
    world.member = MemberFacts(level=None, offshore=False, service_lines=frozenset(), client=True)
    assert await _layer(_person()) == "relationship"


async def test_the_firm_role_decides_when_there_is_one(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, _rule(firm_admin="allow", staff="deny"))
    await authz.authorise_own(_person("firm_admin"), ACTION)
    _set_rule(monkeypatch, _rule(firm_admin="deny", staff="allow"))
    assert await _layer(_person("firm_admin")) == "role"


async def test_without_a_firm_role_a_partner_takes_the_firm_partner_cell(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    world.member = MemberFacts(
        level="partner", offshore=False, service_lines=frozenset(), client=False
    )
    _set_rule(monkeypatch, _rule(firm_partner="allow", staff="deny"))
    await authz.authorise_own(_person(), ACTION)
    _set_rule(monkeypatch, _rule(firm_partner="deny", staff="allow"))
    assert await _layer(_person()) == "role"


async def test_without_a_firm_role_anyone_else_takes_the_staff_cell(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    world.member = MemberFacts(
        level="manager", offshore=False, service_lines=frozenset(), client=False
    )
    _set_rule(monkeypatch, _rule(firm_partner="allow", staff="deny"))
    assert await _layer(_person()) == "role"
    _set_rule(monkeypatch, _rule(firm_partner="deny", staff="allow"))
    await authz.authorise_own(_person(), ACTION)


async def test_a_firm_override_narrows_the_cell(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, _rule(staff="allow"))
    world.overrides[(ACTION, "staff")] = "deny"
    assert await _layer(_person()) == "role"


async def test_a_missing_cell_or_a_conditional_rule_is_refused_at_the_role(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, _rule(firm_admin="allow"))
    assert await _layer(_person()) == "role"  # no `staff` cell at all
    _set_rule(monkeypatch, replace(_rule(staff="allow"), not_offshore=True))
    assert await _layer(_person()) == "role"


async def test_fresh_mfa_is_needed_where_the_action_asks_up_to_fifteen_minutes(
    monkeypatch: pytest.MonkeyPatch, world: World
) -> None:
    _set_rule(monkeypatch, replace(_rule(staff="allow"), mfa_recent=True))
    await authz.authorise_own(_person(mfa_at=NOW - timedelta(minutes=15)), ACTION)
    assert await _layer(_person(mfa_at=NOW - timedelta(minutes=15, seconds=1))) == "attribute"
    assert await _layer(_person(mfa_at=None)) == "attribute"
    _set_rule(monkeypatch, _rule(staff="allow"))  # the action does not ask: stale MFA is fine
    await authz.authorise_own(_person(mfa_at=None), ACTION)


async def test_a_refusal_records_no_check(monkeypatch: pytest.MonkeyPatch, world: World) -> None:
    _set_rule(monkeypatch, _rule(staff="deny"))
    with authz.recording_checks() as checked, pytest.raises(authz.Forbidden):
        await authz.authorise_own(_person(), ACTION)
    assert checked == set()


async def test_an_unknown_action_is_an_error_not_a_refusal(world: World) -> None:
    with pytest.raises(authz.UnknownAction):
        await authz.authorise_own(_person(), "q03t064.not_in_the_matrix")
