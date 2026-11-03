"""N-04-T06 (TASK-3210; DEC-2210): the notices core's pure rules.

Row acceptance: "HOME-01 and NOT-01 read 9 open and 2 New from one provider, a walled user gets
404 with recomputed tallies, and every illegal transition answers 409 with facts." The tallies
and the transition table are pinned here; the HTTP path is
`tests/integration/backfill/test_n04t06_notices_core.py`.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from abacus.modules.notices import service
from abacus.modules.notices.service import Notice

ON = date(2026, 9, 14)


def _n(status: str, respond_by: date | None = None, **kw: object) -> Notice:
    base = Notice(
        id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        client_entity_id=uuid.uuid4(),
        agency="irs",
        agency_name="IRS",
        notice_type_key="cp2000",
        notice_code="CP2000",
        title="Proposed adjustment",
        tax_year=2024,
        form="1040",
        received_on=date(2026, 8, 24),
        notice_date=None,
        respond_by=respond_by,
        respond_by_source=None,
        amount_tax=None,
        amount_interest=None,
        amount_penalty=None,
        amount_total=None,
        interest_to=None,
        taxpayer_tin_last4=None,
        related_return_id=None,
        authorization_kind="form_8821",
        authorization_id=None,
        status=status,
        position=None,
        decision_id=None,
        decided_at=None,
        partner_owned=False,
        follow_up_on=None,
        closed_on=None,
        escalated_reason=None,
        client_visible=False,
        assignee_user_id=None,
        status_changed_at=datetime.now(UTC),
        row_version=1,
    )
    return replace(base, **kw)


def _nine() -> list[Notice]:
    """NOT-01 a: 2 New · 3 Analyzing · 2 Response drafted · 2 Awaiting IRS (9 rows)."""
    return [
        _n("received", date(2026, 9, 21)),
        _n("received", date(2026, 10, 30), authorization_kind="none"),
        _n("classified", date(2026, 9, 23)),
        _n("analyzing", date(2026, 10, 1)),
        _n("analyzing", date(2026, 10, 9), agency="state", notice_type_key="state_generic"),
        _n("response_drafted", date(2026, 10, 2)),
        _n("approved", date(2026, 10, 12)),
        _n("sent", date(2026, 8, 30)),
        _n("awaiting_irs", date(2026, 8, 20)),
    ]


def test_ac1_the_tiles_and_open_count_come_from_one_set_of_rows() -> None:
    counts = service.tallies(_nine(), ON)
    assert counts.tiles == {"new": 2, "analyzing": 3, "response_drafted": 2, "awaiting": 2}
    assert counts.open == 7  # sent and awaiting rows are not open; escalated would be
    assert counts.due_within_7 == 1  # Sep 21 is 7 days out: red
    assert counts.blocked == 1


def test_ac1_a_walled_row_leaves_the_tallies_too() -> None:
    rows = _nine()
    walled = rows[0]
    counts = service.tallies([r for r in rows if r.id != walled.id], ON)
    assert counts.tiles["new"] == 1
    assert counts.due_within_7 == 0


def test_ac1_risk_bands() -> None:
    assert service.risk_band(date(2026, 9, 21), ON, "received") == "red"
    assert service.risk_band(date(2026, 9, 23), ON, "analyzing") == "amber"
    assert service.risk_band(date(2026, 11, 30), ON, "received") == "none"
    assert service.risk_band(date(2026, 9, 15), ON, "sent") == "none"  # not open


@pytest.mark.parametrize(
    ("frm", "to"),
    [
        ("received", "approved"),
        ("received", "sent"),
        ("closed", "classified"),
        ("approved", "closed"),
        ("sent", "approved"),
    ],
)
async def test_ac1_an_illegal_transition_is_409_with_facts(frm: str, to: str) -> None:
    with pytest.raises(service.IllegalTransition) as caught:
        await service.move(
            object(),  # pyright: ignore[reportArgumentType] -- refused before any write
            _n(frm),
            to,
            actor_kind="human",
            actor_user_id=uuid.uuid4(),
        )
    assert caught.value.facts == {"from_status": frm, "to_status": to}


def test_ac1_closed_is_terminal_and_escalated_rows_have_no_tile() -> None:
    assert service.TRANSITIONS["closed"] == frozenset()
    assert _n("escalated").tile is None
    assert _n("escalated").open
