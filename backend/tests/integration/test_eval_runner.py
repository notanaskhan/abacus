"""SPEC-005 AC-1, AC-3, AC-9, AC-14, AC-15 (TASK-020): the runner against a real throwaway stack
(containers), on the fake model. One stack runs three small suites:
- key cases repeat; a deliberately wrong fake answer fails the dangerous metric (negative
  control);
- a tiny cost limit stops the run `aborted_cost` before any case;
- an honest run passes. Each is stored and written as a summary."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus_tools.evals import runner
from abacus_tools.evals.suite import Case, Expected, FakeAnswer, Suite, Threshold

AGENT = "evidence.screener"


def _case(id: str, mutation: str, action: str, answer: str, *, key: bool = False) -> Case:
    return Case(
        id=id,
        mutation=mutation,
        expected=Expected(stage="screened", action=action),  # type: ignore[arg-type] -- literal actions
        fake_answer=FakeAnswer(action=answer, confidence=0.97),  # type: ignore[arg-type] -- literal actions
        key=key,
        fast=True,
    )


def _suite(cases: tuple[Case, ...], *, cost_limit: str = "5") -> Suite:
    return Suite(
        agent=AGENT,
        version=1,
        covers=frozenset(),
        cases=cases,
        graders=(
            "structured_output",
            "citations_verified",
            "untrusted_contained",
            "within_budget",
        ),
        thresholds=(Threshold(metric="needs_revision_recall", minimum=0.97),),
        dangerous_error="needs_revision_recall",
        repeats=3,
        required_pass_rate=0.8,
        calibration_tolerance=0.5,
        cost_limit_usd=Decimal(cost_limit),
    )


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The stack rewrites these process settings; restore them after the test."""
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path / "fake"))
    monkeypatch.delenv("ABACUS_EVAL_SIGNING_KEY", raising=False)


def test_ac1_ac3_ac9_ac15_the_runner_repeats_catches_a_wrong_answer_and_stops_at_its_limit(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    honest = _suite((_case("balanced", "none", "ready_for_review", "ready_for_review", key=True),))
    wrong = _suite(
        (
            _case("balanced", "none", "ready_for_review", "ready_for_review", key=True),
            # Needs revision, but the fake model calls it ready with high confidence.
            _case("wrong_entity", "wrong_entity", "needs_revision", "ready_for_review"),
        )
    )
    tiny = _suite(
        (_case("balanced", "none", "ready_for_review", "ready_for_review"),), cost_limit="0.01"
    )
    try:
        passed, failed, aborted = runner.run(
            AGENT, "small", "full", out, suites=[honest, wrong, tiny]
        )
    finally:
        settings.cache_clear()
    assert passed.status == "passed", passed.reasons
    assert [c.attempt for c in passed.cases] == [1, 2, 3]  # the key case repeated
    assert passed.fake
    assert failed.status == "failed"
    assert "threshold:needs_revision_recall" in failed.reasons
    assert aborted.status == "aborted_cost"
    assert aborted.cases == ()
    written = {json.loads(p.read_text())["status"] for p in out.glob("*.json")}
    assert written == {"passed", "failed", "aborted_cost"}
