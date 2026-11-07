"""N-04-T25 (TASK-6000; DEC-2600): the responder's live rule and its shadow pairs.

N-04 §6: live no earlier than four weeks of shadow, with at least 10 compared notices and no
disagreement on amounts, on top of SPEC-036 Q1 and QD-10. The stage guard asks
`responder_criterion`; the Tuesday window and both founders stay with the people.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from abacus.modules.agents.notice_responder import NO_PROVENANCE, RESPONDER
from abacus.modules.agents.shadow_score import (
    RESPONDER_MIN_COMPARED,
    RESPONDER_MIN_DAYS,
    Pair,
    ResponderShadow,
    responder_criterion,
    score,
)

AS_OF = datetime(2027, 12, 7, 19, tzinfo=UTC)
FIRST = AS_OF - timedelta(days=RESPONDER_MIN_DAYS)


def _agreeing(n: int) -> list[ResponderShadow]:
    return [ResponderShadow("agree", None, "agree") for _ in range(n)]


def test_ac_the_rule_is_four_weeks_and_ten_notices() -> None:
    assert (RESPONDER_MIN_DAYS, RESPONDER_MIN_COMPARED) == (28, 10)


def test_ac_met_after_four_weeks_with_ten_compared_and_no_amount_refusal() -> None:
    assert responder_criterion(FIRST, AS_OF, _agreeing(10)) is None


def test_ac_under_four_weeks_is_refused_first() -> None:
    early = AS_OF - timedelta(days=RESPONDER_MIN_DAYS - 1)
    assert responder_criterion(early, AS_OF, _agreeing(40)) == "n04_shadow_weeks"
    assert responder_criterion(None, AS_OF, _agreeing(40)) == "n04_shadow_weeks"


def test_ac_nine_compared_notices_are_too_few() -> None:
    # A refused answer is a shadow run, never a compared notice.
    shadows = [*_agreeing(9), ResponderShadow(None, "bad_citation", "agree")]
    assert responder_criterion(FIRST, AS_OF, shadows) == "n04_compared_notices"


def test_ac_one_number_without_provenance_blocks_live() -> None:
    shadows = [*_agreeing(30), ResponderShadow(None, NO_PROVENANCE, "disagree")]
    assert responder_criterion(FIRST, AS_OF, shadows) == "n04_amounts"


def test_ac_partial_agrees_with_partially_agree_in_the_qd10_score() -> None:
    pairs = [Pair("partial", "partially_agree"), Pair("agree", "agree"), Pair("disagree", "agree")]
    found = score(
        tenant_id=uuid.uuid4(),
        agent_id=RESPONDER,
        runs=3,
        first_run_at=FIRST,
        pairs=pairs,
        as_of=AS_OF,
    )
    assert (found.scored, found.agreed) == (3, 2)
    assert found.de1_misses == found.de4_misses == found.de5_misses == 0


def test_the_other_agents_scores_keep_their_shape() -> None:
    # A new field would change every stored shadow report's digest (Q-02-T50).
    found = score(
        tenant_id=uuid.UUID(int=1),
        agent_id="evidence.screener",
        runs=0,
        first_run_at=None,
        pairs=[],
        as_of=AS_OF,
    )
    assert set(found.export()) == {
        "algorithm", "tenant_id", "agent_id", "as_of", "runs", "first_run_at", "days", "scored",
        "agreed", "disagreement", "override", "de1_misses", "de4_misses", "de5_misses",
        "spec036_q1", "qd10",
    }  # fmt: skip
