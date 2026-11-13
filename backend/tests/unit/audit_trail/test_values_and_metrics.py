"""The audit values gate and the pilot metric reads, without a database (G-02-T09, Q-04-T006;
SPEC-349 AC-5, AC-10, AC-11; DEC-435, DEC-715; Q-03-T072).

The integration suites prove both against Postgres; these pin the decisions a mutation run
decides on the unit suites alone: the order of the values gate (flag, need to know, resolver),
which right a firm-level event needs, the contract's shape of a resolved answer, the actions the
metrics may read, and the SQL each metric read builds.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from abacus.kernel.errors import NotFound
from abacus.modules.audit_trail import metrics, values
from abacus.modules.platform.api import AuditEventRef, AuditValues
from abacus.modules.platform.audit_slots import AuditNotIncluded, AuditValueRow

metrics_allowed = metrics._allowed  # pyright: ignore[reportPrivateUsage] -- the helper under test
metrics_counts = metrics._counts  # pyright: ignore[reportPrivateUsage] -- the helper under test
metrics_durations = metrics._durations  # pyright: ignore[reportPrivateUsage] -- the helper under test

TENANT = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
ENGAGEMENT = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
PRIYA = uuid.UUID("00000000-0000-4000-8000-000000000007")


class _Ctx:
    def __init__(self) -> None:
        self.tenant_id = TENANT
        self.tenant = object()


def _event(engagement_id: uuid.UUID | None) -> AuditEventRef:
    return AuditEventRef(
        seq=4,
        action="journal_entry.posted",
        target_type="journal_entry",
        target_id="je-1",
        before_ref=None,
        after_ref=None,
        engagement_id=engagement_id,
    )


def _sql(stmt: ClauseElement) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


# --- values: the contract's shape ----------------------------------------------------------------


def test_out_withheld_and_unavailable_carry_status_and_reason_only() -> None:
    withheld = values.out(AuditValues("withheld", reason="need_to_know"))
    assert withheld.status == "withheld"
    assert withheld.reason == "need_to_know"
    assert withheld.rows == []
    assert withheld.not_included == []
    unavailable = values.out(AuditValues("unavailable", rows=(AuditValueRow("amount", "1", "2"),)))
    assert unavailable.status == "unavailable"
    assert unavailable.reason is None
    assert unavailable.rows == []


def test_out_resolved_copies_rows_and_not_included() -> None:
    answer = values.out(
        AuditValues(
            "resolved",
            reason="need_to_know",
            rows=(
                AuditValueRow(
                    "ssn", "•••-••-2208", "•••-••-2209", masked=True, item_label="", amount=None
                ),
                AuditValueRow(
                    "amount", "10.00", "12.00", item_label="Accrued expenses", amount="2.00"
                ),
            ),
            not_included=(
                AuditNotIncluded("Accrued expenses", "review_required", "14900.00", PRIYA),
                AuditNotIncluded("Prepaids", "out_of_scope"),
            ),
        )
    )
    assert answer.status == "resolved"
    assert answer.reason is None
    first, second = answer.rows
    assert first.item_label == "ssn"  # no label: the field names the row
    assert first.field == "ssn"
    assert first.masked is True
    assert (first.before, first.after, first.amount) == ("•••-••-2208", "•••-••-2209", None)
    assert second.item_label == "Accrued expenses"
    assert second.masked is False
    assert (second.before, second.after, second.amount) == ("10.00", "12.00", "2.00")
    routed, plain = answer.not_included
    assert (routed.item_label, routed.reason_code, routed.amount) == (
        "Accrued expenses",
        "review_required",
        "14900.00",
    )
    assert routed.routed_to is not None
    assert routed.routed_to.user_id == PRIYA
    assert routed.routed_to.display_name == ""
    assert (plain.item_label, plain.reason_code, plain.amount, plain.routed_to) == (
        "Prepaids",
        "out_of_scope",
        None,
        None,
    )


# --- values: need to know ------------------------------------------------------------------------


async def test_engagement_event_needs_engagement_read(monkeypatch: pytest.MonkeyPatch) -> None:
    resource = object()
    asked: list[tuple[object, object, tuple[str, ...]]] = []

    async def engagement_resource(tenant: object, engagement_id: uuid.UUID) -> object:
        assert engagement_id == ENGAGEMENT
        return resource

    async def allowed_actions(ctx: object, res: object, actions: tuple[str, ...]) -> set[str]:
        asked.append((ctx, res, actions))
        return {"engagement.read"}

    monkeypatch.setattr(values, "engagement_resource", engagement_resource)
    monkeypatch.setattr(values, "allowed_actions", allowed_actions)
    ctx = _Ctx()
    assert await values.may_see_values(ctx, _event(ENGAGEMENT)) is True  # type: ignore[arg-type] -- a stand-in context
    assert asked == [(ctx, resource, ("engagement.read",))]


async def test_engagement_event_without_the_read_is_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def engagement_resource(tenant: object, engagement_id: uuid.UUID) -> object:
        return object()

    async def allowed_actions(ctx: object, res: object, actions: tuple[str, ...]) -> set[str]:
        return {"engagement.read_metadata"}

    monkeypatch.setattr(values, "engagement_resource", engagement_resource)
    monkeypatch.setattr(values, "allowed_actions", allowed_actions)
    assert await values.may_see_values(_Ctx(), _event(ENGAGEMENT)) is False  # type: ignore[arg-type] -- a stand-in context


async def test_an_engagement_gone_is_withheld(monkeypatch: pytest.MonkeyPatch) -> None:
    async def engagement_resource(tenant: object, engagement_id: uuid.UUID) -> object:
        raise NotFound("engagement")

    async def allowed_actions(ctx: object, res: object, actions: tuple[str, ...]) -> set[str]:
        raise AssertionError("no probe for an engagement that is gone")

    monkeypatch.setattr(values, "engagement_resource", engagement_resource)
    monkeypatch.setattr(values, "allowed_actions", allowed_actions)
    assert await values.may_see_values(_Ctx(), _event(ENGAGEMENT)) is False  # type: ignore[arg-type] -- a stand-in context


async def test_firm_event_needs_the_qm_owners_right(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[object, tuple[str, ...]]] = []

    async def allowed_actions(ctx: object, res: object, actions: tuple[str, ...]) -> set[str]:
        asked.append((res, actions))
        return {"audit_event.read_firm_values"}

    async def engagement_resource(tenant: object, engagement_id: uuid.UUID) -> object:
        raise AssertionError("a firm-level event has no engagement")

    monkeypatch.setattr(values, "allowed_actions", allowed_actions)
    monkeypatch.setattr(values, "engagement_resource", engagement_resource)
    assert await values.may_see_values(_Ctx(), _event(None)) is True  # type: ignore[arg-type] -- a stand-in context
    [(res, actions)] = asked
    assert actions == ("audit_event.read_firm_values",)
    assert res == values.Resource.firm(TENANT)


async def test_firm_event_with_engagement_read_only_is_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allowed_actions(ctx: object, res: object, actions: tuple[str, ...]) -> set[str]:
        return {"engagement.read"}

    monkeypatch.setattr(values, "allowed_actions", allowed_actions)
    assert await values.may_see_values(_Ctx(), _event(None)) is False  # type: ignore[arg-type] -- a stand-in context


# --- values: the gate's order --------------------------------------------------------------------


Gate = dict[str, Any]  # Any: the fakes' mixed state (flags, lists)


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Gate:
    state: Gate = {"flag": True, "see": True, "flags": [], "resolved": []}

    async def flag_enabled(tenant: object, flag: str) -> bool:
        state["flags"].append(flag)
        return bool(state["flag"])

    async def may_see_values(ctx: object, event: AuditEventRef) -> bool:
        return bool(state["see"])

    async def audit_values(ctx: object, event: AuditEventRef) -> AuditValues:
        state["resolved"].append(event.seq)
        return AuditValues("resolved", rows=(AuditValueRow("f", "a", "b"),))

    monkeypatch.setattr(values, "flag_enabled", flag_enabled)
    monkeypatch.setattr(values, "may_see_values", may_see_values)
    monkeypatch.setattr(values, "audit_values", audit_values)
    return state


async def test_values_off_for_the_firm_are_not_enabled(gate: Gate) -> None:
    gate["flag"] = False
    answer = await values.values_for(_Ctx(), _event(ENGAGEMENT))  # type: ignore[arg-type] -- a stand-in context
    assert (answer.status, answer.reason) == ("withheld", "not_enabled")
    assert gate["flags"] == [values.AUDIT_LOG_VALUES]
    assert gate["resolved"] == []


async def test_values_without_need_to_know_are_withheld(gate: Gate) -> None:
    gate["see"] = False
    answer = await values.values_for(_Ctx(), _event(ENGAGEMENT))  # type: ignore[arg-type] -- a stand-in context
    assert (answer.status, answer.reason) == ("withheld", "need_to_know")
    assert gate["resolved"] == []


async def test_values_in_scope_are_the_resolvers(gate: Gate) -> None:
    answer = await values.values_for(_Ctx(), _event(ENGAGEMENT))  # type: ignore[arg-type] -- a stand-in context
    assert answer.status == "resolved"
    assert [(r.field, r.before, r.after) for r in answer.rows] == [("f", "a", "b")]
    assert gate["resolved"] == [4]


# --- metrics -------------------------------------------------------------------------------------

WINDOW = metrics.Window(datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC))


def test_metric_actions_are_requests_portal_sessions_and_evidence() -> None:
    assert {
        "request_item.created",
        "request_item.sent",
        "request_item.uploaded",
        "request_item.returned_to_client",
        "request_item.waived",
        "evidence.uploaded",
        "review_decision.recorded",
        "portal_sign_in.code_requested",
        "session.started",
        "session.ended",
    } == metrics.METRIC_ACTIONS


def test_allowed_sorts_and_dedupes() -> None:
    assert metrics_allowed(["session.started", "evidence.uploaded", "session.started"]) == [
        "evidence.uploaded",
        "session.started",
    ]
    assert metrics_allowed([]) == []


def test_allowed_refuses_any_other_action_by_name() -> None:
    with pytest.raises(metrics.MetricActionRefused) as refused:
        metrics_allowed(["evidence.uploaded", "user.mfa_reset"])
    assert refused.value.args == ("user.mfa_reset",)
    assert isinstance(refused.value, ValueError)


def test_counts_sql_groups_actions_inside_the_window() -> None:
    sql = _sql(metrics_counts(["evidence.uploaded", "session.started"], WINDOW))
    assert sql.startswith("SELECT audit_events.action, count(*) AS n")
    assert "audit_events.action IN ('evidence.uploaded', 'session.started')" in sql
    assert "audit_events.occurred_at >= '2026-09-01 00:00:00+00:00'" in sql
    assert "audit_events.occurred_at < '2026-10-01 00:00:00+00:00'" in sql
    assert sql.rstrip().endswith("GROUP BY audit_events.action")


def test_durations_sql_is_first_start_to_last_end_per_target() -> None:
    sql = _sql(metrics_durations("session.started", "session.ended", WINDOW))
    assert (
        "SELECT s.target_type, s.target_id, "
        "EXTRACT(epoch FROM max(e.occurred_at) - min(s.occurred_at)) AS seconds" in sql
    )
    assert (
        "JOIN audit_events AS e ON e.tenant_id = s.tenant_id AND e.target_type = s.target_type "
        "AND e.target_id = s.target_id" in sql
    )
    assert "s.action = 'session.started'" in sql
    assert "e.action = 'session.ended'" in sql
    assert "s.occurred_at >= '2026-09-01 00:00:00+00:00'" in sql
    assert "e.occurred_at < '2026-10-01 00:00:00+00:00'" in sql
    assert "e.occurred_at >= s.occurred_at" in sql
    assert "GROUP BY s.target_type, s.target_id ORDER BY s.target_type, s.target_id" in sql


class _Row:
    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)


class _Session:
    def __init__(self, rows: list[_Row]) -> None:
        self.rows = rows
        self.statements: list[ClauseElement] = []

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, stmt: ClauseElement) -> list[_Row]:
        self.statements.append(stmt)
        return self.rows


async def test_event_counts_fill_every_asked_action(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session([_Row(action="evidence.uploaded", n=3)])
    tenants: list[object] = []

    def tenant_session(tenant: object) -> _Session:
        tenants.append(tenant)
        return session

    monkeypatch.setattr(metrics, "tenant_session", tenant_session)
    tenant = object()
    counts = await metrics.event_counts(
        tenant,  # type: ignore[arg-type] -- a stand-in tenant
        ["session.started", "evidence.uploaded"],
        WINDOW,
    )
    assert counts == {"evidence.uploaded": 3, "session.started": 0}
    assert list(counts) == ["evidence.uploaded", "session.started"]
    assert tenants == [tenant]
    assert "audit_events.action IN ('evidence.uploaded', 'session.started')" in _sql(
        session.statements[0]
    )


async def test_event_counts_refuse_before_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    def tenant_session(tenant: object) -> _Session:
        raise AssertionError("refused before any session")

    monkeypatch.setattr(metrics, "tenant_session", tenant_session)
    with pytest.raises(metrics.MetricActionRefused):
        await metrics.event_counts(object(), ["audit.read"], WINDOW)  # type: ignore[arg-type] -- a stand-in tenant


async def test_durations_are_typed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session([_Row(target_type="session", target_id="s-1", seconds=90)])

    def tenant_session(tenant: object) -> _Session:
        return session

    monkeypatch.setattr(metrics, "tenant_session", tenant_session)
    found = await metrics.first_to_last_durations(
        object(),  # type: ignore[arg-type] -- a stand-in tenant
        "session.started",
        "session.ended",
        WINDOW,
    )
    assert found == [metrics.TargetDuration("session", "s-1", 90.0)]
    assert isinstance(found[0].seconds, float)
    assert "s.action = 'session.started'" in _sql(session.statements[0])


async def test_durations_refuse_either_action(monkeypatch: pytest.MonkeyPatch) -> None:
    def tenant_session(tenant: object) -> _Session:
        return _Session([])

    monkeypatch.setattr(metrics, "tenant_session", tenant_session)
    with pytest.raises(metrics.MetricActionRefused, match=r"user\.created"):
        await metrics.first_to_last_durations(object(), "session.started", "user.created", WINDOW)  # type: ignore[arg-type] -- a stand-in tenant
    with pytest.raises(metrics.MetricActionRefused, match=r"user\.created"):
        await metrics.first_to_last_durations(object(), "user.created", "session.ended", WINDOW)  # type: ignore[arg-type] -- a stand-in tenant
