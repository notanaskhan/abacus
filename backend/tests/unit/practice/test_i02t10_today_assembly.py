"""I-02-T10 (TASK-7719; I-02 F1, F2; DEC-4722): practice.today's read model, by code over C13.

Row acceptance (Daniel at E0): "3 · 6 · 2 · 0, Due tomorrow 9, Ready for sign-off 4 and Needs you
first §754, Capital Accounts, Final approval". The cells, the urgency order, the cards and the
needs-you-first rows are code's.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from abacus.modules.practice.today.assembly import Item, cards_of, cell_of, tone_of, urgency

TODAY = date(2026, 9, 14)


def _item(
    kind: str,
    due: date | None,
    blocked: bool = False,
    engagement: uuid.UUID | None = None,
    title: str = "",
) -> Item:
    return Item(
        uuid.uuid4(), kind, cell_of(kind), engagement, None, due, blocked, "open", title, "", "/x"
    )


def test_kinds_map_to_the_home_02_cells() -> None:
    assert cell_of("decision") == "decision"
    assert cell_of("sign_off_request") == "sign_off"
    assert cell_of("proposal") == "needs_attention"
    assert cell_of("envelope_countersign") == "signature"
    assert cell_of("send_request") == "approval_send"


def test_urgency_puts_overdue_then_blocked_then_soonest_first() -> None:
    late = _item("decision", TODAY - timedelta(days=1), title="late")
    blocked = _item("sign_off_request", TODAY + timedelta(days=5), blocked=True, title="blocked")
    soon = _item("sign_off_request", TODAY + timedelta(days=1), title="soon")
    undated = _item("decision", None, title="undated")
    ranked = sorted([undated, soon, blocked, late], key=lambda i: urgency(i, TODAY))
    assert [i.title for i in ranked] == ["late", "blocked", "soon", "undated"]


def test_cards_group_by_engagement_most_urgent_first() -> None:
    ridgeline, feld = uuid.uuid4(), uuid.uuid4()
    items = [
        _item("sign_off_request", TODAY + timedelta(days=3), engagement=feld, title="feld"),
        _item(
            "decision", TODAY + timedelta(days=1), blocked=True, engagement=ridgeline, title="754"
        ),
        _item(
            "sign_off_request", TODAY + timedelta(days=1), engagement=ridgeline, title="capital"
        ),
    ]
    cards = cards_of(items, TODAY, {ridgeline: "Ridgeline", feld: "Feld"})
    assert [e for e, _ in cards] == [ridgeline, feld]
    assert [i.title for i in cards[0][1]] == ["754", "capital"]


def test_due_tones() -> None:
    assert (tone_of(-1), tone_of(1), tone_of(7)) == ("red_tint", "amber", "neutral")
