"""I-02-T12 (TASK-7721; I-02 §6; DEC-4724): the scenario's FakeModel briefing output.

`fake_briefing` answers `briefing.today@v1` from the task alone, and its answer passes the
step's own `validate`: every gate covered, every figure a fact reference, no reserved verb.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from abacus.ai_gateway import ContextBuilder
from abacus.modules.agents.blocks import Fact
from abacus.modules.agents.briefing.facts import BriefingFacts, GateFact, fact_id
from abacus.modules.agents.briefing.today import (
    EngagementBriefing,
    fake_briefing,
    input_of,
    validate,
)


@dataclass(frozen=True)
class _Request:
    user: str


def _facts(with_due: bool, with_pbc: bool) -> BriefingFacts:
    g754, gcap = uuid.uuid4(), uuid.uuid4()
    gates = (
        GateFact(g754, "decision", "decision", uuid.uuid4(), None,
                 date(2026, 9, 15) if with_due else None, False, None),
        GateFact(gcap, "sign_off_request", "section", uuid.uuid4(), None, None, True, "upstream"),
    )  # fmt: skip
    facts: dict[str, Fact] = {}
    if with_due:
        fid = fact_id("gate", g754, "due")
        facts[fid] = Fact(id=fid, kind="date", value="2026-09-15", basis="C13 gate due date")
    if with_pbc:
        facts["pbc_received"] = Fact(id="pbc_received", kind="count", value="11", basis="pbc")
        facts["pbc_total"] = Fact(id="pbc_total", kind="count", value="24", basis="pbc")
    return BriefingFacts(uuid.uuid4(), uuid.uuid4(), gates, facts, (), ())


def _answer(facts: BriefingFacts) -> EngagementBriefing:
    given = input_of(facts, "Ridgeline Property Partners, LP", {})
    user = ContextBuilder().task(given.model_dump(), untrusted=("gates",)).build().render()
    return EngagementBriefing.model_validate_json(fake_briefing(_Request(user)))


def test_the_fake_answer_passes_validate_with_due_dates_and_pbc() -> None:
    facts = _facts(with_due=True, with_pbc=True)
    answer = _answer(facts)
    assert validate(answer, facts, {}) == []
    assert {w.gate_id for w in answer.why} == {str(g.gate_id) for g in facts.gates}


def test_a_gate_with_no_fact_to_cite_gets_no_why_line() -> None:
    facts = _facts(with_due=True, with_pbc=False)
    answer = _answer(facts)
    # The blocked sign-off has no due date and there are no PBC counts: no line, so coverage
    # fails and the briefing is stored unverified (code's context line shows instead).
    assert len(answer.why) == 1
    assert validate(answer, facts, {}) == ["gate_coverage"]
