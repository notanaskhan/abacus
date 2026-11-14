"""I-02-T14 (TASK-7937; I-02 §3.7, §6.2; `docs/contracts/today.md`; DEC-60, DEC-4932): Today
questions.

Row acceptance: "Asking 'What happens if Samuel doesn't approve the M-2 fix today?' returns a
cited read-only answer, and 'Approve the four sign-offs' gets a refusal pointing to SHL-12 with no
proposal row written."

Unit level, no database or model: the brief's context lines are code's, the Today session is
recognised by its context kind, a Today turn never plans whatever `workbench.plans` says, a request
to act becomes the read-only notice, availability is read before anything is written, and the
audit event names ids only. The cited answer itself is the frozen `evals/workbench_assistant`
Today cases' to judge (I-02 §6.3) and the full path is I-02-T21's journey.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.practice.today import assembly
from abacus.modules.practice.today.contract import (
    Availability,
    Card,
    CountCell,
    GateRow,
    TodayVM,
)
from abacus.modules.workbench import session_turn_v2, today_questions
from abacus.modules.workbench.sessions import CapabilityUnavailable


def _vm(brief_id: object = None) -> TodayVM:
    row = GateRow(
        gate_id=uuid4(), kind="decision", title="M-2 fix — Ridgeline Holdings LP",
        deep_link="/tax/returns/x", context_line="Waiting on Samuel Ito",
    )  # fmt: skip
    return TodayVM(
        brief_date=date(2025, 9, 14),
        brief_id=brief_id,  # type: ignore[arg-type]
        first_name="Daniel",
        items=11,
        engagements=4,
        cells=[CountCell(kind="decision", count=2, href="/home/approvals?band=decision"),
               CountCell(kind="overdue", count=0, href="/home/approvals?band=overdue")],
        lead_facts=[],
        needs_you_first=[row],
        cards=[Card(engagement_id=uuid4(), label="Ridgeline Holdings LP", rows=[row], more=2,
                    briefing_id=uuid4())],
        groups=[],
        availability=Availability(narrative=True, ask=True),
        status="ready",
    )  # fmt: skip


def test_the_context_lines_are_codes_facts_not_briefing_prose() -> None:
    lines = assembly.question_lines(_vm())
    assert lines[0] == "11 items across 4 engagements"
    assert lines[1] == "Decisions 2"  # a zero cell is left out
    assert lines[2] == (
        "Ridgeline Holdings LP: M-2 fix — Ridgeline Holdings LP (Waiting on Samuel Ito); and 2 more"
    )


@pytest.mark.asyncio
async def test_the_chip_reads_today_and_the_day(monkeypatch: pytest.MonkeyPatch) -> None:
    brief = uuid4()

    async def fake(*_: object) -> TodayVM:
        return _vm(brief)

    monkeypatch.setattr(assembly, "assemble", fake)
    found = await assembly.question_context(SimpleNamespace())  # type: ignore[arg-type]
    assert found.chip_label == "Today · Sun Sep 14"
    assert found.brief_id == brief and len(found.briefing_ids) == 1


def test_a_today_session_is_known_by_its_context_kind() -> None:
    refs = [today_questions.today_ref(date(2025, 9, 14)), {"kind": "capability", "id": "x"}]
    assert today_questions.is_today_session(refs)
    assert session_turn_v2._is_today(refs)  # pyright: ignore[reportPrivateUsage] -- the turn's check
    assert not session_turn_v2._is_today([{"kind": "engagement", "id": "e"}])  # pyright: ignore[reportPrivateUsage]
    assert refs[0] == {"kind": "today_brief", "id": "2025-09-14"}


def test_a_today_turn_never_plans_whatever_workbench_plans_says() -> None:
    source = session_turn_v2.__file__
    body = open(source, encoding="utf-8").read()
    assert "plans = False if today else" in body
    assert 'if today and outcome.failure == "plans_off"' in body
    assert session_turn_v2.TODAY_READ_ONLY == today_questions.READ_ONLY_NOTICE


@pytest.mark.asyncio
async def test_an_unavailable_assistant_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def paused(*_: object) -> str:
        return "paused"

    async def never(*_: object, **__: object) -> object:
        raise AssertionError("nothing is read or written past availability")

    monkeypatch.setattr(today_questions, "firm_capability_blocked", paused)
    monkeypatch.setattr(today_questions, "_today_session", never)
    monkeypatch.setattr(today_questions, "post_message", never)
    with pytest.raises(CapabilityUnavailable) as raised:
        await today_questions.ask(SimpleNamespace(), "What's late?", uuid4(), "k1")  # type: ignore[arg-type]
    assert raised.value.facts == {"reason": "paused"}


@pytest.mark.asyncio
async def test_another_days_brief_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.practice import api as practice_api

    async def ready(*_: object) -> None:
        return None

    async def day(*_: object) -> object:
        return SimpleNamespace(brief_id=uuid4(), brief_date=date(2025, 9, 14), chip_label="",
                               lines=(), briefing_ids=())  # fmt: skip

    monkeypatch.setattr(today_questions, "firm_capability_blocked", ready)
    monkeypatch.setattr(practice_api, "question_context", day)
    with pytest.raises(today_questions.BriefNotCurrent):
        await today_questions.ask(SimpleNamespace(), "What's late?", uuid4(), "k1")  # type: ignore[arg-type]


def test_the_question_text_is_restricted_and_capped_at_1000() -> None:
    from pydantic import ValidationError

    from abacus.modules.workbench.today_questions_contract import TodayQuestionIn

    TodayQuestionIn(text="x" * 1000, brief_id=uuid4())
    with pytest.raises(ValidationError):
        TodayQuestionIn(text="x" * 1001, brief_id=uuid4())
    meta = TodayQuestionIn.model_fields["text"].metadata
    assert any(getattr(m, "level", None) == "restricted" or "restricted" in repr(m) for m in meta)


def test_the_audit_event_names_ids_only() -> None:
    body = open(today_questions.__file__, encoding="utf-8").read()
    start = body.index('"today_brief.question_asked"')
    call = body[start : body.index(")", body.index("after=Ref(", start)) + 1]
    assert "after=Ref(session=session_id, item=posted.item_id)" in call
    assert "body" not in call


def test_a_firm_level_turn_reads_the_firms_readiness_only() -> None:
    from abacus.modules.agents import session_turns

    body = open(session_turns.__file__, encoding="utf-8").read()
    assert "if row.engagement_id is None:  # I-02-T14" in body
    assert callable(session_turns.firm_capability_blocked)
