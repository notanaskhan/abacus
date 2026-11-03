"""Q-03-T064 part 2 (TASK-2824): the identity/authz survivors in the list filters
(`_visible_by_role`, `visible_scope`, `visible_clients`, `visible_items`, `_member_of`,
`holds_engagement_role`, `_g2_blocks_reads`, `_not_walled_client`).

From the contracts in `identity.authz` (ADR-020, ADR-026, ADR-145, ADR-164, DEC-132, DEC-380):
- `visible()` filters reads only, and refuses a read whose rule carries MFA, a reason, a
  notification or a condition (those go through `authorise()`);
- an agent sees only its own engagement's rows, inside its initiator's filter, and only for an
  action its matrix cell allows (`allow`, or `task_scope` with the action in its scope); a
  firm-level agent sees nothing;
- a system run sees only its run's engagement, and only where the `system` cell allows;
- a firm role's `allow` reads everything, its `deny` nothing; otherwise the person reaches the
  engagements where they hold an allowed team role or client grant, and with `independence`
  a staff role reaches a row only when cleared or when G2 does not block the row's read;
- the client scopes exclude walled clients; the portal scope reads the person's active grants of
  that kind; an unknown scope kind is an error;
- `holds_engagement_role` narrows to the person's team role on the row's engagement, or their
  firm role for a firm gate role only.
Each test pins the SQL the filter states (literal binds, PostgreSQL), so a changed clause fails.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import column, literal_column, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnElement

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.authz import UnknownAction, recording_checks
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import AgentContext, AuthContext, SystemContext

_visible_by_role = authz._visible_by_role  # pyright: ignore[reportPrivateUsage] -- the rule under test
_member_of = authz._member_of  # pyright: ignore[reportPrivateUsage] -- the rule under test
_g2_blocks_reads = authz._g2_blocks_reads  # pyright: ignore[reportPrivateUsage] -- the rule under test
_not_walled_client = authz._not_walled_client  # pyright: ignore[reportPrivateUsage] -- the rule under test

TENANT = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
READ = "q03t064v.read"
WRITE = "q03t064v.update"
NOW = datetime(2027, 9, 1, 12, tzinfo=UTC)


def _col(name: str) -> ColumnElement[Any]:  # Any: a bare test column
    return column(name)


def _const(text: str) -> Callable[..., ColumnElement[Any]]:  # Any: a bare SQL fragment
    def build(*_: object) -> ColumnElement[Any]:  # Any: a bare SQL fragment
        return literal_column(text)

    return build


def _cleared(_engagement: object, user: object) -> ColumnElement[Any]:  # Any: a bare fragment
    return literal_column(f"CLEARED_{user}")


def _sql(element: ColumnElement[bool]) -> str:
    return " ".join(
        str(
            element.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        ).split()
    )


def _rule(action: str = READ, **over: object) -> Rule:
    values: dict[str, object] = {
        "action": action,
        "decisions": {},
        "mfa_recent": False,
        "requires_reason": False,
        "notify": False,
    }
    values.update(over)
    return Rule(**values)  # pyright: ignore[reportArgumentType] -- the rule under test


@pytest.fixture(autouse=True)
def _no_line_reach(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The service-line reach is #705's; here it never applies unless a test turns it on."""
    monkeypatch.setattr(authz.LOOKUPS, "service_line_column", None)
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", None)
    monkeypatch.setattr(authz, "_independence", None)
    yield


def _install(monkeypatch: pytest.MonkeyPatch, rule: Rule) -> None:
    monkeypatch.setitem(RULES, rule.action, rule)


def _person(
    firm_role: str | None = None, *, kind: str = "human", user: uuid.UUID | None = None
) -> AuthContext:
    who = user or uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, kind, str(who)),  # pyright: ignore[reportArgumentType] -- test kinds
        who,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- test roles
        NOW,
    )


def _agent(
    scope: frozenset[str] = frozenset(), engagement: uuid.UUID | None = ENGAGEMENT
) -> AgentContext:
    initiator = _person()
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(TENANT, "agent", f"agent:q03.agent:{run}"),
        agent_id="q03.agent",
        agent_run_id=run,
        engagement_id=engagement,
        task_scope=scope,
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


def _system() -> SystemContext:
    run = uuid.uuid4()
    return SystemContext(
        TenantContext(TENANT, "system", f"run:{run}"),
        uuid.uuid4(),
        run,
        ENGAGEMENT,
        context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- a run's context
    )


ENG = _col("engagement_id")  # Any: a bare test column


# --- what visible() accepts ----------------------------------------------------------------------


def test_visible_filters_reads_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(WRITE, decisions={"manager": "allow"}))
    with pytest.raises(ValueError, match="filters reads"):
        _visible_by_role(_person(), WRITE, ENG)


@pytest.mark.parametrize(
    "over",
    [
        {"mfa_recent": True},
        {"requires_reason": True},
        {"notify": True},
        {"level_in": frozenset({"partner"})},
    ],
)
def test_visible_refuses_a_read_it_cannot_condition(
    monkeypatch: pytest.MonkeyPatch,
    over: dict[str, Any],  # Any: Rule's own field types
) -> None:
    _install(monkeypatch, _rule(decisions={"manager": "allow"}, **over))
    with pytest.raises(ValueError, match="use authorise"):
        _visible_by_role(_person(), READ, ENG)


def test_an_unknown_action_is_refused() -> None:
    with pytest.raises(UnknownAction):
        _visible_by_role(_person(), "q03t064v.nothing_like_it", ENG)


def test_building_the_filter_records_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"firm_admin": "allow"}))
    with recording_checks() as checked:
        _visible_by_role(_person("firm_admin"), READ, ENG)
    assert checked == {READ}


# --- agents and system runs ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "scope", "sees"),
    [
        ("allow", frozenset[str](), True),
        ("task_scope", frozenset({READ}), True),
        ("task_scope", frozenset({"other.read"}), False),
        ("deny", frozenset({READ}), False),
        (None, frozenset({READ}), False),
    ],
)
def test_an_agent_sees_only_what_its_cell_allows(
    monkeypatch: pytest.MonkeyPatch, cell: str | None, scope: frozenset[str], sees: bool
) -> None:
    decisions = {"manager": "allow", **({"agent": cell} if cell else {})}
    _install(monkeypatch, _rule(decisions=decisions))
    sql = _sql(_visible_by_role(_agent(scope), READ, ENG))
    if sees:
        assert sql.startswith(f"engagement_id = '{ENGAGEMENT}' AND ")
        assert "engagement_members.role IN ('manager')" in sql  # the initiator's own reach
    else:
        assert sql == "false"


def test_a_firm_level_agent_lists_no_engagement_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"agent": "allow", "manager": "allow"}))
    assert _sql(_visible_by_role(_agent(engagement=None), READ, ENG)) == "false"


def test_the_initiator_filter_is_built_without_their_service_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[bool] = []

    def line_reach(*_: object) -> None:
        seen.append(authz._delegating.get())  # pyright: ignore[reportPrivateUsage] -- DEC-383
        return None

    monkeypatch.setattr(authz, "_line_reach", line_reach)
    _install(monkeypatch, _rule(decisions={"agent": "allow", "manager": "allow"}))
    _visible_by_role(_agent(), READ, ENG)
    assert seen == [True]
    assert authz._delegating.get() is False  # pyright: ignore[reportPrivateUsage] -- reset after


@pytest.mark.parametrize(("cell", "sees"), [("allow", True), ("deny", False), (None, False)])
def test_a_system_run_sees_only_its_engagement_where_allowed(
    monkeypatch: pytest.MonkeyPatch, cell: str | None, sees: bool
) -> None:
    _install(monkeypatch, _rule(decisions={"system": cell} if cell else {}))
    sql = _sql(_visible_by_role(_system(), READ, ENG))
    assert sql == (f"engagement_id = '{ENGAGEMENT}'" if sees else "false")


# --- people --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("cell", "sql"), [("allow", "true"), ("deny", "false")])
def test_a_firm_role_cell_decides_outright(
    monkeypatch: pytest.MonkeyPatch, cell: str, sql: str
) -> None:
    _install(monkeypatch, _rule(decisions={"firm_admin": cell, "manager": "allow"}))
    assert _sql(_visible_by_role(_person("firm_admin"), READ, ENG)) == sql


def test_no_allowed_role_and_no_line_reach_sees_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"manager": "deny", "staff": "deny"}))
    assert _sql(_visible_by_role(_person(), READ, ENG)) == "false"


def test_a_person_reaches_engagements_holding_an_allowed_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        _rule(decisions={"manager": "allow", "staff": "deny", "client_admin": "allow"}),
    )
    person = _person()
    sql = _sql(_visible_by_role(person, READ, ENG))
    assert "engagement_members.role IN ('manager')" in sql
    assert f"engagement_members.tenant_id = '{TENANT}'" in sql
    assert f"engagement_members.user_id = '{person.user_id}'" in sql
    assert "'staff'" not in sql
    assert (
        "client_access_grants.scope_kind = 'engagement'" in sql
    )  # the client role through its grants
    assert " OR " in sql


def test_the_line_reach_joins_the_team_reach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "_line_reach", _const("LINE_REACH"))
    _install(monkeypatch, _rule(decisions={"manager": "allow"}))
    sql = _sql(_visible_by_role(_person(), READ, ENG))
    assert sql.endswith("OR LINE_REACH")
    _install(monkeypatch, _rule(decisions={"manager": "deny"}))
    assert _sql(_visible_by_role(_person(), READ, ENG)) == "LINE_REACH"


def test_independence_without_its_registration_reaches_no_staff_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _rule(decisions={"manager": "allow"}, independence=True))
    assert _sql(_visible_by_role(_person(), READ, ENG)) == "false"


def test_independence_keeps_client_roles_and_clears_staff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authz, "_independence", (_cleared, None))
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", _const("ATTEST"))
    _install(
        monkeypatch,
        _rule(decisions={"manager": "allow", "client_admin": "allow"}, independence=True),
    )
    person = _person()
    sql = _sql(_visible_by_role(person, READ, ENG))
    assert "client_access_grants.scope_kind = 'engagement'" in sql
    assert "engagement_members.role IN ('manager')" in sql
    assert f"CLEARED_{person.user_id} OR NOT (" in sql
    assert "firm_setting_values.key = 'g2_blocks_view'" in sql
    assert "firm_setting_values.value IS true" in sql
    assert "AND ATTEST" in sql


def test_support_skips_the_independence_split(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"manager": "allow"}, independence=True))
    sql = _sql(_visible_by_role(_person(kind="support"), READ, ENG))
    assert "engagement_members.role IN ('manager')" in sql


def test_independence_with_only_client_roles_needs_no_clearance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _rule(decisions={"client_admin": "allow"}, independence=True))
    sql = _sql(_visible_by_role(_person(), READ, ENG))
    assert "client_access_grants.scope_kind = 'engagement'" in sql and "g2_blocks_view" not in sql


# --- the helpers ---------------------------------------------------------------------------------


def test_member_of_splits_staff_and_client_roles() -> None:
    person = _person()
    assert _sql(_member_of(person, ENG, [])) == "false"
    staff = _sql(_member_of(person, ENG, ["manager", "senior"]))
    assert staff.startswith("engagement_id IN (SELECT engagement_members.engagement_id")
    assert "engagement_members.role IN ('manager', 'senior')" in staff
    assert " OR " not in staff
    both = _sql(_member_of(person, ENG, ["manager", "client_admin"]))
    assert (
        "engagement_members.role IN ('manager')" in both
        and "client_access_grants.scope_kind = 'engagement'" in both
    )
    assert " OR " in both


def test_g2_blocks_reads_is_the_setting_and_the_attest_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = _person()
    alone = _sql(_g2_blocks_reads(person, ENG))
    assert alone.startswith("EXISTS (SELECT firm_setting_values.key")
    assert f"firm_setting_values.tenant_id = '{TENANT}'" in alone
    assert "AND ATTEST" not in alone
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", _const("ATTEST"))
    assert _sql(_g2_blocks_reads(person, ENG)).endswith(") AND ATTEST")


def test_a_walled_client_is_excluded_by_its_own_wall() -> None:
    person = _person()
    sql = _sql(_not_walled_client(person, _col("client_id")))
    assert sql.startswith("NOT (EXISTS (SELECT ethical_walls.id FROM ethical_walls")
    for part in (
        f"ethical_walls.tenant_id = '{TENANT}'",
        f"ethical_walls.user_id = '{person.user_id}'",
        "ethical_walls.status = 'active'",
        "ethical_walls.client_id = client_id",
    ):
        assert part in sql, part


@pytest.mark.parametrize(
    ("firm_role", "firm_match"),
    [("quality_partner", True), ("firm_admin", False), (None, False)],
)
def test_holds_engagement_role_is_the_team_role_or_a_firm_gate_role(
    firm_role: str | None, firm_match: bool
) -> None:
    person = _person(firm_role)
    sql = _sql(authz.holds_engagement_role(person, ENG, _col("role")))
    for part in (
        "EXISTS (SELECT engagement_members.engagement_id FROM engagement_members",
        f"engagement_members.tenant_id = '{TENANT}'",
        f"engagement_members.user_id = '{person.user_id}'",
        "engagement_members.engagement_id = engagement_id",
        "engagement_members.role = role",
    ):
        assert part in sql, part
    if firm_match:
        assert sql.endswith(f"OR role = '{firm_role}'")
    else:
        assert " OR " not in sql  # `false()` drops out: the team role only


# --- visible_scope and visible_clients -----------------------------------------------------------


def test_the_engagement_scopes_are_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"firm_admin": "allow"}))
    person = _person("firm_admin")
    for scope in ("engagement", "work_item"):
        assert _sql(authz.visible_scope(person, READ, scope, ENG)) == _sql(
            authz.visible(person, READ, ENG)
        )


def test_a_client_scope_filters_reads_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(WRITE, decisions={"firm_admin": "allow"}))
    with pytest.raises(ValueError, match="filters reads"):
        authz.visible_scope(_person("firm_admin"), WRITE, "client", _col("client_id"))


def test_a_firm_role_allow_reads_every_unwalled_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"firm_admin": "allow"}))
    person = _person("firm_admin")
    with recording_checks() as checked:
        sql = _sql(authz.visible_scope(person, READ, "client", _col("client_id")))
    assert checked == {READ}
    assert sql == _sql(_not_walled_client(person, _col("client_id")))


def test_client_scopes_without_their_builder_admit_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authz, "_clients_of_engagements", None)
    _install(monkeypatch, _rule(decisions={"manager": "allow"}))
    with recording_checks() as checked:
        sql = _sql(authz.visible_scope(_person(), READ, "client_entity", _col("client_id")))
    assert sql == "false" and checked == {READ}


def test_client_scopes_read_the_clients_of_admitted_engagements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def clients_of(admitted: Callable[[object], ColumnElement[bool]]) -> object:
        seen.append(_sql(admitted(_col("e"))))
        return select(_const("CLIENTS")())

    monkeypatch.setattr(authz, "_clients_of_engagements", clients_of)
    _install(monkeypatch, _rule(decisions={"manager": "allow"}))
    person = _person()
    sql = _sql(authz.visible_scope(person, READ, "client", _col("client_id")))
    assert sql.startswith("client_id IN (SELECT CLIENTS) AND NOT (EXISTS (SELECT ethical_walls.id")
    assert seen and "engagement_members.role IN ('manager')" in seen[0]


def test_the_portal_scope_reads_the_persons_active_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"client_admin": "allow"}))
    person = _person()
    sql = _sql(
        authz.visible_scope(person, READ, "portal_scope", _col("scope_id"), grant_kind="room")
    )
    assert sql.startswith("scope_id IN (SELECT client_access_grants.scope_id")
    for part in (
        f"client_access_grants.tenant_id = '{TENANT}'",
        f"client_access_grants.user_id = '{person.user_id}'",
        "client_access_grants.scope_kind = 'room'",
        "client_access_grants.status = 'active'",
        "client_access_grants.expires_at IS NULL OR "
        "client_access_grants.expires_at > clock_timestamp()",
    ):
        assert part in sql, part


def test_the_portal_scope_needs_a_person_and_a_grant_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"client_admin": "allow"}))
    assert _sql(authz.visible_scope(_person(), READ, "portal_scope", _col("s"))) == "false"
    assert (
        _sql(authz.visible_scope(_agent(), READ, "portal_scope", _col("s"), grant_kind="room"))
        == "false"
    )


def test_an_unknown_scope_kind_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(decisions={"client_admin": "allow"}))
    with pytest.raises(ValueError, match="unknown scope kind"):
        authz.visible_scope(_person(), READ, "galaxy", _col("s"))  # pyright: ignore[reportArgumentType] -- the refusal


async def test_visible_clients_filters_reads_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, _rule(WRITE, decisions={"firm_partner": "allow"}))
    with pytest.raises(ValueError, match="filters reads"):
        await authz.visible_clients(_person(), WRITE, _col("client_id"))


@pytest.mark.parametrize(
    ("firm_role", "kind", "partner", "cell", "derived"),
    [
        (None, "human", True, "allow", True),  # a partner-level member reads every client
        ("firm_admin", "human", True, "allow", True),  # whose firm role doesn't allow it
        (None, "human", False, "allow", False),  # not partner level
        (None, "support", True, "allow", False),  # support never takes the derived cell
        (None, "human", True, "deny", False),  # the matrix doesn't give firm_partner the read
    ],
)
async def test_visible_clients_derives_the_firm_partner_cell(
    monkeypatch: pytest.MonkeyPatch,
    firm_role: str | None,
    kind: str,
    partner: bool,
    cell: str,
    derived: bool,
) -> None:
    async def partner_level(_ctx: object) -> bool:
        return partner

    monkeypatch.setattr(authz, "_partner_level", partner_level)
    monkeypatch.setattr(authz, "_clients_of_engagements", None)
    _install(monkeypatch, _rule(decisions={"firm_partner": cell, "firm_admin": "deny"}))
    person = _person(firm_role, kind=kind)
    with recording_checks() as checked:
        sql = _sql(await authz.visible_clients(person, READ, _col("client_id")))
    assert checked == {READ}
    if derived:
        assert sql == _sql(_not_walled_client(person, _col("client_id")))
    else:
        assert sql == "false"  # fell through to visible_scope, which has no builder here


async def test_a_firm_role_that_already_allows_takes_the_ordinary_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[object] = []

    async def partner_level(ctx: object) -> bool:
        asked.append(ctx)
        return True

    monkeypatch.setattr(authz, "_partner_level", partner_level)
    _install(monkeypatch, _rule(decisions={"firm_partner": "allow", "firm_admin": "allow"}))
    person = _person("firm_admin")
    sql = _sql(await authz.visible_clients(person, READ, _col("client_id")))
    assert sql == _sql(_not_walled_client(person, _col("client_id")))
    assert asked == []  # the firm role allowed it; the level was never read


# --- visible_items -------------------------------------------------------------------------------


def test_visible_items_adds_the_client_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "_engagement_client", None)
    _install(
        monkeypatch,
        _rule(
            decisions={
                "manager": "allow",
                "client_admin": "client_visible_only",
                "client_contributor": "assigned_only",
                "staff": "assigned_only",  # a staff role never takes a client condition
            }
        ),
    )
    person = _person()
    sql = _sql(
        authz.visible_items(person, READ, ENG, _col("client_visible"), _col("client_assignee_id"))
    )
    assert "client_visible IS true" in sql
    assert f"client_assignee_id = '{person.user_id}'" in sql
    assert (
        sql.count("client_access_grants.scope_kind = 'engagement'") == 2
    )  # one grant reach per client condition
    assert "NOT (EXISTS (SELECT ethical_walls.id" in sql
    assert sql.count("client_visible IS true") == 2


def test_visible_items_without_client_conditions_is_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _rule(decisions={"manager": "allow", "client_admin": "allow"}))
    person = _person()
    got = authz.visible_items(person, READ, ENG, _col("v"), _col("a"))
    assert _sql(got) == _sql(authz.visible(person, READ, ENG))


def test_visible_items_for_an_agent_is_its_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(
        monkeypatch,
        _rule(decisions={"agent": "allow", "manager": "allow", "client_admin": "assigned_only"}),
    )
    agent = _agent()
    got = authz.visible_items(agent, READ, ENG, _col("v"), _col("a"))
    assert _sql(got) == _sql(authz.visible(agent, READ, ENG))
