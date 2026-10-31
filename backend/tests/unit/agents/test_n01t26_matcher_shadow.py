"""N-01-T26 (TASK-2334; DEC-1380): the matcher's shadow score and its cost gate.

Acceptance (the task row): "A committed Bedrock report passes and live stage waits on the shadow
override rate staying within 8 %." The Bedrock report is the operator's (the runbook); here: a
matcher run scored against the person's triage decision, the 8 % tolerance as the live guard reads
it, and the protected cost baseline with its +10 % gate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abacus.modules.agents.shadow_score import MATCHER, matcher_pair, score
from abacus.modules.communications.api import TriageOutcome
from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.runner import baseline

AT = datetime(2027, 7, 1, 12, tzinfo=UTC)
REQUEST = uuid.uuid4()


def _decided(
    decision: str, kind: str | None = None, dest: uuid.UUID | None = None
) -> TriageOutcome:
    return TriageOutcome(uuid.uuid4(), decision, kind, dest, AT)


def test_ac_filing_where_the_matcher_proposed_agrees() -> None:
    pair = matcher_pair(("request", REQUEST), _decided("file", "request", REQUEST))
    assert (pair.action, pair.decision) == ("propose", "followed")


def test_ac_filing_elsewhere_ignoring_or_holding_a_proposal_overrides_it() -> None:
    other = uuid.uuid4()
    for decided in (
        _decided("file", "request", other),
        _decided("file", "permanent_file", REQUEST),
        _decided("ignore"),
        _decided("hold"),
    ):
        assert matcher_pair(("request", REQUEST), decided).decision == "overridden"


def test_ac_a_none_fit_run_agrees_with_ignore_or_hold_and_not_with_a_filing() -> None:
    assert matcher_pair(None, _decided("ignore")).decision == "followed"
    assert matcher_pair(None, _decided("hold")).decision == "followed"
    assert matcher_pair(None, _decided("file", "request", REQUEST)).decision == "overridden"


def _score(overridden: int, total: int = 25) -> bool:
    pairs = [
        matcher_pair(("request", REQUEST), _decided("file", "request", REQUEST))
        for _ in range(total - overridden)
    ] + [matcher_pair(("request", REQUEST), _decided("ignore")) for _ in range(overridden)]
    return score(
        tenant_id=uuid.uuid4(),
        agent_id=MATCHER,
        runs=50,
        first_run_at=AT - timedelta(days=14),
        pairs=pairs,
        as_of=AT,
    ).qd10


def test_ac_live_waits_on_the_shadow_override_rate_staying_within_8_percent() -> None:
    assert _score(2) is True  # 2 of 25 = 8 %: within
    assert _score(3) is False  # 12 %: the live stage waits
    assert _score(0, total=24) is False  # under 25 scored: too few to judge (fail closed)


def test_ac_a_scope_breach_on_an_overridden_run_blocks_live() -> None:
    pairs = [
        matcher_pair(("request", REQUEST), _decided("file", "request", REQUEST)) for _ in range(24)
    ] + [matcher_pair(("request", REQUEST), _decided("ignore"), "scope_breach")]
    found = score(
        tenant_id=uuid.uuid4(),
        agent_id=MATCHER,
        runs=50,
        first_run_at=AT - timedelta(days=14),
        pairs=pairs,
        as_of=AT,
    )
    assert found.de4_misses == 1 and found.qd10 is False


def test_ac_the_protected_cost_baseline_gates_at_ten_percent_over() -> None:
    found = baseline(MATCHER, "small")
    assert found is not None and found == Decimal("0.015")
    assert found * (1 + COST_TOLERANCE) == Decimal("0.0165")


def test_ac_the_intake_section_fails_past_ten_percent_over_its_baseline() -> None:
    from abacus_tools.evals.matching import intake_cost_gate

    base = Decimal("0.015")
    assert intake_cost_gate([Decimal("0.0160"), Decimal("0.0165")], base, real=True) == []
    assert intake_cost_gate([Decimal("0.0166"), Decimal("0.0170")], base, real=True) == [
        "cost_regression"
    ]
    assert intake_cost_gate([Decimal("0.01")], None, real=True) == ["cost_regression:no_baseline"]
    assert intake_cost_gate([], None, real=False) == []  # a fake run spends nothing


def test_ac_the_eval_cli_takes_the_bedrock_route_without_a_direct_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus_tools.evals import runner

    class Settings:
        environment = "evaluation"
        allow_real_model_locally = False
        anthropic_api_key = None

    monkeypatch.setattr(runner, "settings", lambda: Settings())

    def enabled(route: str) -> bool:
        return route == "bedrock"

    monkeypatch.setattr(runner, "route_enabled", enabled)
    runner.guard_real("bedrock")  # no Anthropic key needed: the eval account's AWS role
    with pytest.raises(runner.RefusedEnvironment):
        runner.guard_real("direct")
