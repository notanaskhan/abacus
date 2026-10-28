"""Q-02-T50 (DEC-811; SPEC-036 Q1; chapter 10 QD-10; chapter 05 §5.5.7): the shadow score and the
override rate. Hand-computed agreement, override rate and disagreement reproduce exactly; each
criterion passes or fails at its edge; the export is deterministic, and its digest changes with any
scored fact."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from abacus.modules.agents.shadow_score import Pair, ShadowScore, override_rate, score

FIRM = UUID("00000000-0000-4000-8000-0000000000a1")
AS_OF = datetime.fromisoformat("2027-06-21T12:00:00-05:00")
AGREE_READY = Pair("ready_for_review", "accept")
AGREE_RETURN = Pair("needs_revision", "send_back")
OVERRULED = Pair("needs_revision", "accept")  # the person accepted what the agent flagged
FALSE_CLEARANCE = Pair("ready_for_review", "reject")  # DE-1


def run(pairs: list[Pair], runs: int = 60, days: int = 20) -> ShadowScore:
    return score(
        tenant_id=FIRM,
        agent_id="evidence.screener",
        runs=runs,
        first_run_at=AS_OF - timedelta(days=days),
        pairs=pairs,
        as_of=AS_OF,
    )


def test_the_override_rate_is_rejected_plus_edited_over_decided() -> None:
    found = override_rate(150, 56, 3410)  # chapter 05 §5.5.7: 206 of 3,410
    assert (found.rate, found.enough, found.algorithm) == (
        Decimal("0.0604"),
        True,
        "override_rate.v1",
    )
    assert override_rate(2, 0, 24).rate is None  # under 25 decided: too few to judge
    assert override_rate(2, 0, 25).rate == Decimal("0.0800")
    with pytest.raises(ValueError):
        override_rate(20, 10, 25)


def test_a_hand_computed_shadow_reproduces_exactly() -> None:
    # 30 scored: 20 ready-and-accepted, 8 returned-and-sent-back, 2 flagged-but-accepted.
    found = run([AGREE_READY] * 20 + [AGREE_RETURN] * 8 + [OVERRULED] * 2)
    assert (found.scored, found.agreed) == (30, 28)
    assert found.disagreement == "0.0667"  # 2 / 30
    assert found.override.rate == Decimal("0.0667")
    assert (found.de1_misses, found.de4_misses, found.de5_misses) == (0, 0, 0)
    assert (found.spec036_q1, found.qd10, found.passes) == (True, True, True)


@pytest.mark.parametrize(
    ("runs", "days", "q1"), [(50, 14, True), (49, 30, False), (80, 13, False)]
)
def test_spec036_q1_at_its_edges(runs: int, days: int, q1: bool) -> None:
    assert run([AGREE_READY] * 25, runs=runs, days=days).spec036_q1 is q1


def test_qd10_at_its_edges() -> None:
    assert run([AGREE_READY] * 24).qd10 is False  # 24 scored
    assert run([AGREE_READY] * 23 + [OVERRULED] * 2).qd10 is True  # 2/25 = 8.00%
    assert run([AGREE_READY] * 22 + [OVERRULED] * 3).qd10 is False  # 12%
    assert run([AGREE_READY] * 50 + [OVERRULED] * 4).disagreement == "0.0741"
    assert run([AGREE_READY] * 50 + [OVERRULED] * 4).qd10 is True


@pytest.mark.parametrize(
    "miss",
    [
        FALSE_CLEARANCE,
        Pair("needs_revision", "reject", "scope_breach"),
        Pair("needs_revision", "send_back", "reserved_action"),
    ],
)
def test_one_de1_de4_or_de5_miss_fails_qd10(miss: Pair) -> None:
    found = run([AGREE_READY] * 40 + [miss])
    assert found.qd10 is False
    assert found.de1_misses + found.de4_misses + found.de5_misses == 1


def test_nothing_scored_cannot_go_live() -> None:
    found = run([])
    assert (found.disagreement, found.override.rate, found.qd10) == (None, None, False)


def test_the_export_is_deterministic_and_its_digest_follows_the_facts() -> None:
    a = run([AGREE_READY] * 30)
    b = run([AGREE_READY] * 30)
    assert a.canonical() == b.canonical() and a.sha256 == b.sha256
    assert run([AGREE_READY] * 29 + [OVERRULED]).sha256 != a.sha256
    assert run([AGREE_READY] * 30, runs=61).sha256 != a.sha256
    export = a.export()
    assert export["algorithm"] == "shadow_score.v1"
    assert export["as_of"] == AS_OF.isoformat()
    assert a.override.rate == Decimal("0.0000") and isinstance(export["override"], dict)
