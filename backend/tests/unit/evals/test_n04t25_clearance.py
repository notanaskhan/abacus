"""N-04-T25 (TASK-6000; DEC-2600): the responder's real-run clearance, per mode.

Acceptance (the task row): "Clearance is recorded only for modes that pass every threshold on
Bedrock, and no pilot firm is above shadow stage at M15." Here: the report's per-mode verdict, the
signature, the protected cost rows, and the spec turning `cleared` only with every mode recorded.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from abacus.modules.agents.spec import spec
from abacus_tools.evals.notices_responder import load, run
from abacus_tools.evals.notices_responder_real import (
    MODES,
    Seen,
    clearance,
    facts_of,
    graded,
    signed,
    verified,
)
from abacus_tools.evals.runner import baseline
from abacus_tools.evals.summary import SIGNING_KEY_ENV

REPO = Path(__file__).resolve().parents[4]
CLEARANCE = REPO / "evals" / "notices_responder" / "clearance.yaml"
SUITE = load()
REVIEWED = SUITE.model_copy(update={"label_review": "reviewed"})
BASELINES: dict[str, Decimal | None] = {"analyze": Decimal("0.25"), "extract": Decimal("0.08")}


def _seen(mode: str, cost: str = "0.05", answered: bool = True) -> Seen:
    return Seen("c", mode, 1, Decimal(cost), {"x": 1} if answered else None)


SEEN = [_seen("analyze"), _seen("extract", "0.02")]


def test_ac_a_clean_bedrock_run_clears_both_modes() -> None:
    found = clearance(REVIEWED, "bedrock", [], SEEN, BASELINES)
    assert {m: found[m]["cleared"] for m in MODES} == {"analyze": True, "extract": True}


def test_ac_the_direct_route_never_clears() -> None:
    found = clearance(REVIEWED, "direct", [], SEEN, BASELINES)
    assert all(not found[m]["cleared"] and "not_bedrock" in found[m]["reasons"] for m in MODES)


def test_ac_a_failed_threshold_blocks_only_its_mode() -> None:
    found = clearance(REVIEWED, "bedrock", ["extract.field_exact_match.degraded"], SEEN, BASELINES)
    assert found["analyze"]["cleared"] is True
    assert found["extract"]["reasons"] == ["extract.field_exact_match.degraded"]


def test_ac_consent_refusal_blocks_both_modes() -> None:
    found = clearance(REVIEWED, "bedrock", ["consent_refusal"], SEEN, BASELINES)
    assert not found["analyze"]["cleared"] and not found["extract"]["cleared"]


def test_ac_analyze_waits_on_the_label_review() -> None:
    assert SUITE.label_review == "pending"
    found = clearance(SUITE, "bedrock", [], SEEN, BASELINES)
    assert found["analyze"]["reasons"] == ["label_review_pending"]
    assert found["extract"]["cleared"] is True


def test_ac_an_errored_attempt_or_no_attempt_fails_closed() -> None:
    found = clearance(
        REVIEWED, "bedrock", [], [*SEEN, _seen("analyze", answered=False)], BASELINES
    )
    assert found["analyze"]["reasons"] == ["errored"]
    found = clearance(REVIEWED, "bedrock", [], [_seen("analyze")], BASELINES)
    assert found["extract"]["reasons"] == ["no_attempts"]


def test_ac_cost_over_ten_percent_or_no_baseline_fails() -> None:
    found = clearance(REVIEWED, "bedrock", [], [_seen("analyze", "0.30"), *SEEN[1:]], BASELINES)
    assert found["analyze"]["reasons"] == ["cost_regression"]
    found = clearance(REVIEWED, "bedrock", [], SEEN, {"analyze": None, "extract": Decimal("0.08")})
    assert found["analyze"]["reasons"] == ["cost_regression:no_baseline"]


def test_the_protected_cost_rows_are_the_spec_budgets() -> None:
    responder = spec("notices.responder")
    assert baseline("notices.responder", "medium") == responder.limits.max_cost_usd
    assert baseline("notices.responder", "small") == responder.modes["extract"].max_cost_usd


def test_ac_a_report_is_signed_and_a_changed_one_does_not_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIGNING_KEY_ENV, "test-only-key")
    report = signed({"route": "bedrock", "status": "passed"})
    assert verified(report)
    assert not verified({**report, "status": "failed"})
    monkeypatch.delenv(SIGNING_KEY_ENV)
    assert "signature" not in signed({"route": "bedrock"})


def test_ac_client_data_turns_cleared_only_with_every_mode_recorded() -> None:
    record = yaml.safe_load(CLEARANCE.read_text(encoding="utf-8"))
    assert record["agent"] == "notices.responder"
    recorded = set(record["modes"] or {})
    assert recorded <= set(MODES)
    for mode in recorded:
        entry = record["modes"][mode]
        assert len(entry["report_sha256"]) == 64 and entry["signature"] and entry["recorded_by"]
    if spec("notices.responder").client_data == "cleared":
        assert recorded == set(MODES), "client_data: cleared needs every mode in clearance.yaml"


def test_real_attempts_grade_with_the_fake_runs_graders() -> None:
    cases = [c for c in SUITE.cases if c.fast]
    seen = [
        Seen(c.id, c.mode, 1, Decimal(0), c.fake_answer.model_dump(mode="json")) for c in cases
    ]
    by_attempts = run(SUITE, subset="fast", attempts=graded(SUITE, cases, seen))
    assert by_attempts.metrics == run(SUITE, subset="fast").metrics


def test_the_eval_hands_the_responder_codes_facts() -> None:
    case = next(c for c in SUITE.cases if c.mode == "analyze")
    facts = facts_of(case)
    assert [r["key"] for r in facts.rows] == [r.key for r in case.rows]
    assert facts.options == tuple(case.options)
    assert {h for h, _ in facts.lines} == {ln.ref for ln in case.document_lines}
