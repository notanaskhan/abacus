"""T-02-T13 (TASK-2322; T-02 §3.3; DEC-1368): the pipeline is derived from the return's status, the
Team ladder reads the C3 sign-offs (a stale one is not done), and the engine summary keeps only
well-formed lines from an approved import."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from abacus.modules.engagements.api import WorkItemFacts
from abacus.modules.tax import board, overview


def _states(status: str) -> dict[str, str]:
    return {p.step: p.state for p in overview._pipeline(status)}  # pyright: ignore[reportPrivateUsage] -- the derivation itself


def test_the_pipeline_follows_the_status() -> None:
    assert _states("not_started") == {
        "gather": "not_started",
        "prepare": "not_started",
        "review": "not_started",
        "deliver": "not_started",
    }
    assert _states("in_review") == {
        "gather": "done",
        "prepare": "done",
        "review": "in_progress",
        "deliver": "not_started",
    }
    assert _states("awaiting_signature")["deliver"] == "in_progress"
    assert _states("accepted")["deliver"] == "done"


PREPARER, DETAIL, MANAGER, SIGNER = (uuid.uuid4() for _ in range(4))
NAMES = {
    PREPARER: "Kevin Osei",
    DETAIL: "Olivia Brandt",
    MANAGER: "Samuel Ito",
    SIGNER: "Daniel Reyes",
}


def _loaded(status: str) -> overview.Loaded:
    facts = WorkItemFacts(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "Jonah & Claire Feld",
        None,
        {
            "preparer": (PREPARER,),
            "detail_reviewer": (DETAIL,),
            "manager_reviewer": (MANAGER,),
            "signer": (SIGNER,),
        },
    )
    row = board.ReturnRow(
        facts.work_item_id, "1040", 2025, status, "manager", True, False, None, None, None
    )
    return overview.Loaded(facts, row, 3, "cch_axcess", "2025I:FeldJ", None, uuid.uuid4(), ())


def test_the_ladder_reads_the_feld_state_a() -> None:
    sep8 = datetime(2026, 9, 8, 15, 0, tzinfo=UTC)
    sep9 = datetime(2026, 9, 9, 15, 0, tzinfo=UTC)
    states = {1: (PREPARER, sep8, False), 2: (DETAIL, sep9, False)}
    ladder = overview._ladder(_loaded("in_review"), states, NAMES)  # pyright: ignore[reportPrivateUsage] -- the ladder itself
    assert [(s.step, s.state, s.note) for s in ladder] == [
        ("preparer", "done", "Kevin Osei · submitted Sep 8"),
        ("detail_review", "done", "Olivia Brandt · signed off Sep 9"),
        ("manager_review", "in_progress", "Samuel Ito · in progress"),
        ("final_approval", "not_started", "Daniel Reyes · signer"),
    ]


def test_a_stale_sign_off_is_not_done() -> None:
    states = {1: (PREPARER, datetime(2026, 9, 8, tzinfo=UTC), True)}
    ladder = overview._ladder(_loaded("preparing"), states, NAMES)  # pyright: ignore[reportPrivateUsage] -- the ladder itself
    assert ladder[0].state == "in_progress"


def test_only_well_formed_summary_lines_are_kept() -> None:
    lines = overview._lines(  # pyright: ignore[reportPrivateUsage] -- the line reader itself
        [
            {"line_key": "refund", "label": "Refund", "amount": "253", "total": "grand"},
            {"line_key": "2a", "label": "Tax-exempt interest", "amount": None},
            {"label": "no key"},
            "not a line",
        ]
    )
    assert [(x.line_key, x.amount, x.total) for x in lines] == [
        ("refund", Decimal("253"), "grand"),
        ("2a", None, None),
    ]


def test_dates_are_written_as_the_handoff_does() -> None:
    assert overview._day(date(2026, 9, 8)) == "Sep 8"  # pyright: ignore[reportPrivateUsage] -- the date wording
