"""Q-03-T064: the service-line reach (G-01-T12, DEC-380; ADR-183 rule 6; DEC-383), the
identity/authz survivors in `_line_reader_cell`, `_may_read_lines`, `_line_reader` and
`_line_reach`.

From the contracts in `identity.authz`:
- the reader's cell is the `staff` engagement role's allow, for a plain read only (no MFA, reason,
  notify or condition);
- a person reads through a line only as themselves (never support, a client, a metadata-only firm
  role, or an agent run delegating to them);
- `_line_reader`: the firm opened a line the person holds, the engagement is on it, and its
  client is known not to be an attest client; every unknown fact refuses;
- `_line_reach` is the same rule in SQL: an enabled policy whose content is visible to the line,
  never `audit`; an active, onshore, non-admin staff membership holding the line; an attest-free
  client; no team role on the engagement; no firm override of the `staff` cell for the action.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import column, literal_column
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnElement

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.authz.matrix import Rule
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import FirmPolicy, MemberFacts

_line_reader_cell = authz._line_reader_cell  # pyright: ignore[reportPrivateUsage] -- the rule under test
_may_read_lines = authz._may_read_lines  # pyright: ignore[reportPrivateUsage] -- the rule under test
_delegating = authz._delegating  # pyright: ignore[reportPrivateUsage] -- the rule under test
_line_reader = authz._line_reader  # pyright: ignore[reportPrivateUsage] -- the rule under test
_line_reach = authz._line_reach  # pyright: ignore[reportPrivateUsage] -- the rule under test

READ = "q03t064.read"
WRITE = "q03t064.update"
TENANT, ENGAGEMENT = uuid.uuid4(), uuid.uuid4()


def _rule(action: str = READ, **cells: str) -> Rule:
    return Rule(
        action=action,
        decisions={"staff": "allow", **cells},  # pyright: ignore[reportArgumentType] -- test cells
        mfa_recent=False,
        requires_reason=False,
        notify=False,
    )


def _person(
    firm_role: str | None = None, *, kind: str = "human", client: bool = False
) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, kind, str(user)),  # pyright: ignore[reportArgumentType] -- test kinds
        user,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- test roles
        datetime.now(UTC),
        client=client,
    )


# --- the reader's cell ---------------------------------------------------------------------------


def test_the_reader_cell_is_staffs_allow_on_a_plain_read() -> None:
    assert _line_reader_cell(_rule()) == "allow"


@pytest.mark.parametrize(
    "rule",
    [
        _rule(WRITE),
        replace(_rule(), mfa_recent=True),
        replace(_rule(), requires_reason=True),
        replace(_rule(), notify=True),
        replace(_rule(), not_offshore=True),
        replace(_rule(), decisions={"staff": "deny"}),
        replace(_rule(), decisions={"manager": "allow"}),
    ],
    ids=["write", "mfa", "reason", "notify", "condition", "staff-denied", "no-staff-cell"],
)
def test_anything_but_a_plain_staff_read_has_no_reader_cell(rule: Rule) -> None:
    assert _line_reader_cell(rule) is None


# --- who may read through a line -----------------------------------------------------------------


def test_a_staff_member_may_read_lines() -> None:
    assert _may_read_lines(_person(), _rule()) is True
    assert _may_read_lines(_person("practice_leader"), _rule()) is True


@pytest.mark.parametrize(
    "ctx",
    [
        _person(kind="support"),
        _person(client=True),
        _person("firm_admin"),
        _person("security_admin"),
    ],
    ids=["support", "client", "firm-admin", "security-admin"],
)
def test_support_clients_and_metadata_only_roles_never_read_lines(ctx: AuthContext) -> None:
    assert _may_read_lines(ctx, _rule()) is False


def test_an_agent_delegating_to_a_person_never_inherits_their_line() -> None:
    token = _delegating.set(True)
    try:
        assert _may_read_lines(_person(), _rule()) is False
    finally:
        _delegating.reset(token)


def test_a_rule_without_a_reader_cell_reads_no_line() -> None:
    assert _may_read_lines(_person(), _rule(WRITE)) is False


# --- the reader, fact by fact --------------------------------------------------------------------


class Facts:
    def __init__(self) -> None:
        self.opened: frozenset[str] = frozenset({"tax"})
        self.member: MemberFacts | None = MemberFacts(
            level="senior", offshore=False, service_lines=frozenset({"tax"}), client=False
        )
        self.line: str | None = "tax"
        self.attest: bool | None = False


@pytest.fixture
def facts(monkeypatch: pytest.MonkeyPatch) -> Iterator[Facts]:
    found = Facts()

    async def policy(*_: object) -> FirmPolicy:
        return FirmPolicy(overrides={}, settings_on=frozenset(), line_reach=found.opened)

    async def member(*_: object) -> MemberFacts | None:
        return found.member

    async def line_of(*_: object) -> str | None:
        return found.line

    async def attest_of(*_: object) -> bool | None:
        return found.attest

    monkeypatch.setattr(authz, "firm_policy", policy)
    monkeypatch.setattr(authz, "member_facts", member)
    monkeypatch.setattr(authz.LOOKUPS, "service_line", line_of)
    monkeypatch.setattr(authz.LOOKUPS, "attest", attest_of)
    yield found


async def _reads(ctx: AuthContext | None = None) -> bool:
    return await _line_reader(ctx or _person(), _rule(), ENGAGEMENT)


async def test_an_open_line_the_person_holds_on_an_attest_free_client_reads(facts: Facts) -> None:
    assert await _reads() is True


async def test_every_unknown_or_closed_fact_refuses(
    facts: Facts, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts.opened = frozenset()
    assert await _reads() is False
    facts.opened = frozenset({"advisory"})  # open, but not a line the person holds
    assert await _reads() is False
    facts.opened = frozenset({"tax"})
    for member in (
        None,
        MemberFacts(level="senior", offshore=False, service_lines=frozenset({"tax"}), client=True),
        MemberFacts(level="senior", offshore=True, service_lines=frozenset({"tax"}), client=False),
        MemberFacts(level="admin", offshore=False, service_lines=frozenset({"tax"}), client=False),
    ):
        facts.member = member
        assert await _reads() is False, member
    facts.member = MemberFacts(
        level=None, offshore=False, service_lines=frozenset({"tax"}), client=False
    )
    assert await _reads() is True  # no level is not admin
    facts.line = "cas"
    assert await _reads() is False
    facts.line = None
    assert await _reads() is False
    facts.line = "tax"
    for attest in (True, None):
        facts.attest = attest
        assert await _reads() is False, attest
    facts.attest = False
    monkeypatch.setattr(authz.LOOKUPS, "service_line", None)
    assert await _reads() is False


async def test_a_person_who_may_not_read_lines_is_refused_before_any_lookup(facts: Facts) -> None:
    facts.member = None  # would refuse anyway; the point is the early return
    assert await _reads(_person("firm_admin")) is False


# --- the same rule in SQL ------------------------------------------------------------------------


def _sql(element: ColumnElement[bool]) -> str:
    return " ".join(
        str(
            element.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )


def _line_column(_engagement: object) -> ColumnElement[str]:
    return literal_column("'LINE'")


def _attest_column(_engagement: object) -> ColumnElement[bool]:
    return literal_column("ATTEST")


@pytest.fixture
def columns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz.LOOKUPS, "service_line_column", _line_column)
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", _attest_column)


def test_the_sql_reach_is_none_when_it_cannot_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz.LOOKUPS, "service_line_column", None)
    monkeypatch.setattr(authz.LOOKUPS, "attest_column", _attest_column)
    assert _line_reach(_person(), READ, _rule(), column("engagement_id")) is None


def test_the_sql_reach_is_none_for_someone_who_may_not_read_lines(columns: None) -> None:
    assert _line_reach(_person("firm_admin"), READ, _rule(), column("engagement_id")) is None


def test_the_sql_reach_states_each_part_of_the_rule(columns: None) -> None:
    ctx = _person()
    reach = _line_reach(ctx, READ, _rule(), column("engagement_id"))
    assert reach is not None
    sql = _sql(reach)
    tenant, user = str(ctx.tenant_id), str(ctx.user_id)
    for part in (
        # the firm opened the line, content visible to it, never audit
        "'LINE' IN (SELECT service_line_policies.service_line FROM service_line_policies",
        f"service_line_policies.tenant_id = '{tenant}'",
        "service_line_policies.enabled IS true",
        "service_line_policies.content_visible_to = 'service_line'",
        "service_line_policies.service_line != 'audit'",
        # an active, onshore, non-admin staff membership holding the line
        "EXISTS (SELECT memberships.user_id FROM memberships",
        f"memberships.tenant_id = '{tenant}'",
        f"memberships.user_id = '{user}'",
        "memberships.kind = 'staff'",
        "memberships.status = 'active'",
        "memberships.offshore IS false",
        "memberships.level IS NULL OR memberships.level != 'admin'",
        "'LINE' = ANY (memberships.service_lines)",
        # an attest-free client
        "ATTEST IS false",
        # no team role on the engagement
        "(engagement_id NOT IN (SELECT engagement_members.engagement_id FROM engagement_members",
        f"engagement_members.tenant_id = '{tenant}'",
        f"engagement_members.user_id = '{user}'",
        # no firm override of the staff cell for this action
        "NOT (EXISTS (SELECT firm_policy_overrides.action FROM firm_policy_overrides",
        f"firm_policy_overrides.tenant_id = '{tenant}'",
        f"firm_policy_overrides.action = '{READ}'",
        "firm_policy_overrides.role = 'staff'",
    ):
        assert part in sql, part
