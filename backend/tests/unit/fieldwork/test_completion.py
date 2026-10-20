"""SPEC-301 (TASK-302): severity folded by code, entries balanced by code, representation gaps by
code; only the partner concludes severity."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.modules.fieldwork.completion import (
    CompletionInvalid,
    LineIn,
    check_lines,
    deficiency_of,
    gaps_of,
    status_of,
)
from abacus.modules.fieldwork.models import AdjustmentEvent, FindingCommunication, FindingSeverity
from abacus.modules.identity.authz.matrix import RULES

T0 = datetime(2026, 10, 20, 9, tzinfo=UTC)
U = uuid.uuid4()


def _sev(stage: str, severity: str, minutes: int) -> FindingSeverity:
    row = SimpleNamespace(  # a fake stands in for the row
        stage=stage,
        severity=severity,
        set_by=U,
        created_at=T0 + timedelta(minutes=minutes),
        rationale="r" if stage == "concluded" else None,
    )
    return cast(FindingSeverity, row)


def _told(minutes: int) -> FindingCommunication:
    row = SimpleNamespace(  # a fake stands in for the row
        created_at=T0 + timedelta(minutes=minutes),
        communicated_on=date(2026, 10, 21),
        recipients="Audit committee",
    )
    return cast(FindingCommunication, row)


def test_ac4_balanced_entries_pass_and_return_their_total() -> None:
    lines = [
        LineIn("5000", Decimal("68400"), Decimal(0)),
        LineIn("2000", Decimal(0), Decimal("68400")),
    ]
    assert check_lines(lines) == Decimal("68400")


@pytest.mark.parametrize(
    "lines",
    [
        [LineIn("5000", Decimal(10), Decimal(0))],  # one line
        [LineIn("5000", Decimal(10), Decimal(0)), LineIn("2000", Decimal(0), Decimal(9))],
        [LineIn("5000", Decimal(10), Decimal(10)), LineIn("2000", Decimal(0), Decimal(0))],
        [LineIn(" ", Decimal(10), Decimal(0)), LineIn("2000", Decimal(0), Decimal(10))],
    ],
)
def test_ac4_unbalanced_or_two_sided_lines_are_refused(lines: list[LineIn]) -> None:
    with pytest.raises(CompletionInvalid):
        check_lines(lines)


def test_ac5_status_follows_the_events() -> None:
    def ev(kind: str) -> AdjustmentEvent:
        return cast(AdjustmentEvent, SimpleNamespace(kind=kind))  # a fake stands in for the row

    assert status_of([]) == "proposed"
    assert status_of([ev("approved")]) == "approved"
    assert status_of([ev("approved"), ev("client_declined")]) == "client_declined"


def test_ac1_ac3_severity_states() -> None:
    names = {U: "Dana"}
    assert deficiency_of([], [], names) is None
    proposed = deficiency_of([_sev("proposed", "deficiency", 0)], [], names)
    assert proposed is not None and proposed.status == "proposed" and proposed.concluded is None
    concluded = deficiency_of(
        [_sev("concluded", "significant_deficiency", 5), _sev("proposed", "deficiency", 0)],
        [_told(1)],  # before the conclusion: doesn't count
        names,
    )
    assert concluded is not None and concluded.status == "concluded"
    assert concluded.concluded == "significant_deficiency" and concluded.proposed == "deficiency"
    told = deficiency_of([_sev("concluded", "material_weakness", 5)], [_told(9)], names)
    assert told is not None and told.status == "communicated"
    assert told.communicated_to == "Audit committee"


def test_ac8_gaps_are_concluded_findings_and_passed_entries_without_a_representation() -> None:
    f1, f2, a1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rep: Any = SimpleNamespace(finding_id=f1, adjustment_id=None)  # a fake row
    gaps = gaps_of([rep], {f1: "Covered", f2: "Payroll approvals"}, {a1: "AJE-3"})
    assert [(g.kind, g.label) for g in gaps] == [
        ("finding", "Payroll approvals"),
        ("adjustment", "AJE-3"),
    ]


def test_ac2_only_the_partner_concludes_and_the_agent_does_nothing() -> None:
    conclude = RULES["finding.conclude_severity"].decisions
    assert conclude.get("engagement_partner") == "allow" and "manager" not in conclude
    for action in (
        "finding.propose_severity",
        "finding.conclude_severity",
        "finding.communicate",
        "adjustment.propose",
        "adjustment.approve",
        "adjustment.record_response",
        "representation.edit",
    ):
        assert RULES[action].decisions.get("agent") == "deny"
    assert "senior" not in RULES["adjustment.approve"].decisions
