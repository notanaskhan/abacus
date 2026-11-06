"""N-04-T24 (ADR-078): N-04's red rules, written outside the implementing session: G3 for a notice
engagement, the CP2000 and CP14 maps from the handoff's own figures, and capability refusals that
leave no recommendation, whichever way the agent's hook fails. Citation and number provenance
rejection and containment on notice text are held by the responder's suites
(unit/agents/test_n04t19_notice_responder.py, unit/evals/test_n04t18_notices_responder.py)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import gate_policy
from abacus.modules.evidence.form_extraction import extract, identify
from abacus.modules.evidence.words import PageWords, Word
from abacus.modules.notices import analysis


def _line(top: float, *tokens: str) -> list[Word]:
    words: list[Word] = []
    x = 72.0
    for token in tokens:
        width = 6.0 * len(token)
        words.append(Word(token, x, top, x + width, top + 10.0, 1.0))
        x += width + 4.0
    return words


def _page(*lines: list[Word]) -> PageWords:
    return PageWords(1, 612.0, 792.0, 0, tuple(w for line in lines for w in line))


_TENANT = TenantContext(uuid4(), "system", "test")


def test_a_notice_engagement_needs_the_letter_alone() -> None:
    assert set(gate_policy.required_gates("notice_response", ())) == {"G3"}


def test_the_whitley_cp2000_is_identified_with_its_year() -> None:
    page = _page(_line(40, "Notice", "CP2000"), _line(60, "Tax", "year:", "2024"))
    found = identify([page])
    assert found is not None
    assert found.form_type == "cp2000"
    assert found.tax_year == 2024


def test_the_santos_cp14_reads_its_amount_owed() -> None:
    page = _page(
        _line(40, "Notice", "CP14"),
        _line(60, "Tax", "year:", "2024"),
        _line(100, "Amount", "you", "owed"),
        _line(120, "Amount", "due:", "1,106.00"),
    )
    found = identify([page])
    assert found is not None
    assert "1106.00" in {f.value_text for f in extract(found, [page])}


@pytest.mark.parametrize("stage", ["off", "shadow", "refused"])
async def test_no_stage_but_live_keeps_a_recommendation(stage: str) -> None:
    async def hook(_t: object, _n: object, _f: object) -> analysis.AgentStep:
        return analysis.AgentStep(stage, uuid4(), "agree")

    analysis.register_agent_step(hook)
    found = await analysis._agent_step(_TENANT, uuid4(), {})
    assert found.stage == stage
    assert found.recommended_position is None


async def test_a_failing_hook_fails_closed() -> None:
    async def hook(_t: object, _n: object, _f: object) -> analysis.AgentStep:
        raise RuntimeError("provider terms")

    analysis.register_agent_step(hook)
    found = await analysis._agent_step(_TENANT, uuid4(), {})
    assert (found.stage, found.run_id, found.recommended_position) == ("refused", None, None)
