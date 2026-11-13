"""I-02-T10 (TASK-7719; I-02 F1, F2; DEC-4722): practice.today's read model, by code over C13.

Row acceptance (Daniel at E0): "3 · 6 · 2 · 0, Due tomorrow 9, Ready for sign-off 4 and Needs you
first §754, Capital Accounts, Final approval". The cells, the urgency order, the cards and the
needs-you-first rows are code's.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

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


# --- S41 gaps (DEC-4734): High risk, Running and the drill-in's downstream rows ------------------


def test_high_risk_reads_only_ready_briefings_risk_lines() -> None:
    from dataclasses import dataclass

    from abacus.modules.practice.today import assembly

    @dataclass(frozen=True)
    class _B:
        status: str
        blocks: object

    risk = {"version": 1, "parts": [{"kind": "p", "segments": [{"kind": "text", "text": "K-1s"}]}]}
    ready, unverified, plain = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    groups = assembly._high_risk(  # pyright: ignore[reportPrivateUsage] -- the module's own rule
        {
            ready: _B("ready", {"summary": {}, "risk": risk}),
            unverified: _B("unverified", {"summary": {}, "risk": risk}),
            plain: _B("ready", {"summary": {}, "risk": None}),
        },
        {ready: "Ridgeline", unverified: "Feld", plain: "Harborview"},
    )
    assert [(g.key, g.count) for g in groups] == [("high_risk", 1)]
    assert groups[0].items[0].title == "Ridgeline"
    assert groups[0].items[0].detail_blocks == [risk]
    assert assembly._high_risk({}, {}) == []  # pyright: ignore[reportPrivateUsage] -- the module's own rule


def test_downstream_rows_come_from_the_hooks_both_sides_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    import abacus.modules.engagements.api as engagements_api
    from abacus.modules.practice.today import assembly

    feld = uuid.uuid4()

    async def visible(_ctx: object, kind: str, _wi: uuid.UUID, _eng: uuid.UUID) -> list[uuid.UUID]:
        assert kind == "tax_return"
        return [feld]

    async def milestone(_ctx: object, _kind: str, _wi: uuid.UUID) -> str | None:
        return "K-1 release"

    async def titles(_tenant: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {feld: "Feld 2025 Form 1040"}

    monkeypatch.setattr(engagements_api, "dependents_visible", visible)
    monkeypatch.setattr(engagements_api, "next_milestone", milestone)
    monkeypatch.setattr(engagements_api, "work_item_titles", titles)

    class _Ctx:
        tenant: object = None

    rows = asyncio.run(
        assembly._downstream(_Ctx(), uuid.uuid4(), uuid.uuid4())  # type: ignore[arg-type] -- a test double for the person's context
    )
    assert [(r.title, r.state_line, r.deep_link) for r in rows] == [
        ("Feld 2025 Form 1040", "Waiting on the K-1 release", f"/tax-returns/{feld}")
    ]
    assert asyncio.run(assembly._downstream(_Ctx(), uuid.uuid4(), None)) == []  # type: ignore[arg-type] -- a test double for the person's context
