"""T-08-T44 (TASK-8919; T-08 AC2.13; DF-10; FD-1; DEC-5921; amber): the firm's deadline overrides.

Row acceptance: "Firm override rows are versioned and owner-published, platform rows stay
read-only, and a postponement applied by notice id moves only that client's dates on HOME-03."
Here: the `deadline_overrides` kind is a firm standard (the K-02 lifecycle the other kinds use:
versioned, owner-drafted, published by a person) and its payload validates; the internal target
is code's (offset, then earlier past weekends, holidays and firm closures) and never moves a
statutory date; a relief application moves only its own client's tax dates whose original falls
in the notice's window, never earlier; and the pins name the versions read. The DB path (publish,
apply, recompute) is the integration test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from abacus.modules.methodology.standards_contract import (
    DeadlineOverridesPayload,
    FirmStandardKind,
    StandardPayload,
)
from abacus.modules.platform.api import FilingDeadlineFact
from abacus.modules.practice import deadline_overrides as df10

V_FIRM = UUID(int=1)
V_PLATFORM = UUID(int=2)
HOLIDAYS = frozenset({date(2026, 9, 7)})  # Labor Day


def test_the_kind_is_a_firm_standard_and_its_payload_validates() -> None:
    from typing import get_args

    assert "deadline_overrides" in get_args(FirmStandardKind)
    payload = TypeAdapter[StandardPayload](StandardPayload).validate_python(
        {"kind": "deadline_overrides",
         "offsets": [{"form": "1065", "internal_offset_days": 14}],
         "closures": [{"date": "2026-09-04", "name": "Firm offsite"}],
         "postponements": [{"notice_id": "IL-2026-03", "title": "Illinois storm relief",
                            "window_start": "2026-08-01", "window_end": "2026-10-31",
                            "postponed_to": "2026-11-16"}]}
    )  # fmt: skip
    assert isinstance(payload, DeadlineOverridesPayload)
    with pytest.raises(ValidationError):
        DeadlineOverridesPayload.model_validate(
            {
                "kind": "deadline_overrides",
                "offsets": [{"form": "1065", "internal_offset_days": 0}],
            }
        )


def test_the_internal_target_is_a_working_day_before_the_statutory_date() -> None:
    # Tue Sep 15, 2026 less 14 days is Tue Sep 1; less 8 is Mon Sep 7 (Labor Day), so Fri Sep 4,
    # and with the firm offsite that Friday, Thu Sep 3.
    assert df10.internal_target(date(2026, 9, 15), 14, frozenset(), HOLIDAYS) == date(2026, 9, 1)
    assert df10.internal_target(date(2026, 9, 15), 8, frozenset(), HOLIDAYS) == date(2026, 9, 4)
    offsite = frozenset({date(2026, 9, 4)})
    assert df10.internal_target(date(2026, 9, 15), 8, offsite, HOLIDAYS) == date(2026, 9, 3)
    assert df10.internal_target(date(2026, 9, 15), 12, frozenset(), HOLIDAYS) == date(2026, 9, 3)


NOTICE = df10.Notice(
    "IL-2026-03", date(2026, 8, 1), date(2026, 10, 31), date(2026, 11, 16), "firm", V_FIRM
)


def test_a_notice_moves_a_covered_date_later_never_earlier() -> None:
    assert df10.postponed(date(2026, 9, 15), date(2026, 9, 15), NOTICE) == date(2026, 11, 16)
    assert df10.postponed(date(2026, 3, 16), date(2026, 9, 15), NOTICE) is None  # not covered
    late = df10.Notice(
        "X-1", date(2026, 8, 1), date(2026, 10, 31), date(2026, 9, 1), "firm", V_FIRM
    )
    assert df10.postponed(date(2026, 9, 15), date(2026, 9, 15), late) is None  # never earlier


def _fact(client: UUID, *, kind: str = "tax_return", line: str = "tax") -> FilingDeadlineFact:
    return FilingDeadlineFact(
        source_kind=kind, source_ref=str(uuid4()), filing_label="Form 1065 · 2025",
        client_id=client, office_id=None, service_line=line,
        original_due_on=date(2026, 9, 15), due_on=date(2026, 9, 15), stage_code="in_progress",
        rule_key="1065",
    )  # fmt: skip


def test_a_relief_application_moves_only_its_clients_tax_dates() -> None:
    mine, other = uuid4(), uuid4()
    app = df10.Application(uuid4(), mine, NOTICE, datetime(2026, 9, 10, tzinfo=UTC))
    overrides = df10.Overrides(V_FIRM, {"1065": 14}, frozenset(), {NOTICE.notice_id: NOTICE})
    facts = [_fact(mine), _fact(other), _fact(mine, kind="close", line="cas")]
    out = df10.apply_overrides(facts, overrides, {mine: [app]}, HOLIDAYS)
    (f1, t1, a1, m1), (f2, t2, a2, m2), (f3, t3, a3, m3) = out
    assert (a1, m1) == (app, date(2026, 11, 16))  # that client's return moves
    assert t1 == date(2026, 11, 2)  # its internal target follows the moved date (Nov 16 less 14)
    assert (a2, m2) == (None, None) and t2 == date(2026, 9, 1)  # another client: statutory
    assert (a3, m3, t3) == (None, None, None)  # a close is not tax relief, and has no offset
    assert f1 is facts[0] and f2 is facts[1] and f3 is facts[2]


def test_without_firm_overrides_nothing_changes() -> None:
    facts = [_fact(uuid4())]
    assert df10.apply_overrides(facts, None, {}, HOLIDAYS) == [(facts[0], None, None, None)]


def test_the_migration_and_registry() -> None:
    from pathlib import Path

    from abacus.modules.practice import registry

    root = Path(__file__).resolve().parents[3]
    migration = (root / "migrations/versions/1016_deadline_overrides.py").read_text("utf-8")
    assert "'deadline_overrides'" in migration and "postponement_applications" in migration
    assert "actor_kind = 'human'" in migration
    assert "postponement_applications" in registry.INSERT_ONLY
    assert "postponement_applications" in registry.TABLES
