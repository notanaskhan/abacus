"""TASK-020 (SPEC-005): the evaluation runner's own logic, without containers: suite validation
(AC-2, AC-4, AC-7), graders and the model judge (AC-5, AC-6), metrics, calibration (AC-8, AC-9),
the gate and verdict (AC-9, AC-12), the cost limit (AC-15), summaries and their signatures, the
publish checks (AC-13, AC-14), mutations, the environment guard (AC-16), and the generated
`_eval_suites` constant."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.ai_gateway import MODELS, Attribution, GatewayResult, prompt
from abacus.kernel.db import TenantContext
from abacus_tools.codegen import eval_suites
from abacus_tools.evals import cases, graders, metrics, publish, runner, summary
from abacus_tools.evals.calibration import calibrate, expected_calibration_error
from abacus_tools.evals.gate import reasons
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import (
    Case,
    Expected,
    FakeAnswer,
    InvalidSuite,
    Suite,
    Threshold,
    load,
    validate,
)
from abacus_tools.evals.taxonomy import (
    ADVERSARIAL_CATEGORIES,
    FAILURE_CATEGORIES,
    REQUIRED_COVERAGE,
)
from abacus_tools.evals.verdict import Verdict, judge
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import trial_balance_document

REPO = Path(__file__).resolve().parents[5]
SUITE = REPO / "evals" / "screening" / "suite.yaml"


def _validate(suite: Suite) -> None:
    validate(
        suite,
        graders=frozenset(graders.GRADERS),
        metrics=frozenset(metrics.METRICS),
        mutations=cases.MUTATION_CATEGORIES,
    )


EVERYTHING = FAILURE_CATEGORIES | ADVERSARIAL_CATEGORIES


def _case(
    id: str = "a",
    *,
    stage: str = "screened",
    action: str | None = "ready_for_review",
    mutation: str = "none",
    categories: frozenset[str] = frozenset(),
    fast: bool = True,
    key: bool = True,
) -> Case:
    return Case(
        id=id,
        mutation=mutation,
        categories=categories,
        expected=Expected.model_validate({"stage": stage, "action": action}),
        fake_answer=FakeAnswer(action="ready_for_review", confidence=0.9),
        fast=fast,
        key=key,
    )


def _covering() -> tuple[Case, ...]:
    """One case per required category, with the matching mutation."""
    covering = [
        _case(c, mutation=c, categories=frozenset({c}), stage="failed_validation", action=None)
        for c in sorted(EVERYTHING)
    ]
    return (*covering, _case("ok"))


def _suite(**changes: object) -> Suite:
    base: dict[str, object] = {
        "agent": "evidence.screener",
        "version": 1,
        "covers": EVERYTHING,
        "cases": _covering(),
        "graders": ("structured_output",),
        "thresholds": (Threshold(metric="needs_revision_recall", minimum=0.97),),
        "dangerous_error": "needs_revision_recall",
        "repeats": 2,
        "required_pass_rate": 1.0,
        "calibration_tolerance": 0.1,
        "cost_limit_usd": Decimal(5),
    }
    base.update(changes)
    return Suite.model_validate(base)


def _seen(**kw: object) -> Observation:
    base: dict[str, object] = {
        "case_id": "a",
        "attempt": 1,
        "stage": "screened",
        "action": "ready_for_review",
        "model_action": "ready_for_review",
        "confidence": 0.9,
        "citations_verified": True,
        "contained": True,
        "cost_usd": Decimal("0.001"),
        "budget_usd": Decimal("0.03"),
    }
    base.update(kw)
    return Observation(**base)  # type: ignore[arg-type] -- built from a loose dict for brevity


# --- suites --------------------------------------------------------------------------------------


def test_ac2_the_screeners_suite_file_loads_and_validates() -> None:
    suite = load(SUITE)
    _validate(suite)
    assert suite.agent == "evidence.screener"
    assert suite.dangerous_error == "needs_revision_recall"
    assert suite.sampling == {"temperature": 0.0}


def test_ac4_the_screeners_suite_covers_what_its_agent_requires() -> None:
    suite = load(SUITE)
    assert suite.covers >= REQUIRED_COVERAGE["evidence.screener"] == EVERYTHING


def test_ac4_the_original_cases_are_kept_and_the_injections_are_key() -> None:
    suite = {c.id: c for c in load(SUITE).cases}
    assert {"odd_account_name", "tag_breakout", "low_confidence"} <= set(suite)
    for key in (
        "wrong_entity",
        "incomplete",
        "low_confidence",
        "prompt_injection",
        "tag_breakout",
    ):
        assert suite[key].key, key


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"graders": ("nope",)}, "unknown grader"),
        (
            {
                "thresholds": (
                    Threshold(metric="needs_revision_recall", minimum=0.9),
                    Threshold(metric="nope", minimum=0.5),
                )
            },
            "unknown metric",
        ),
        (
            {"thresholds": (Threshold(metric="ready_precision", minimum=0.5),)},
            "has no threshold",
        ),
        (
            {
                "thresholds": (Threshold(metric="accuracy", minimum=0.9),),
                "dangerous_error": "accuracy",
            },
            "accuracy is never the dangerous error",
        ),
        (
            {
                "thresholds": (
                    Threshold(metric="needs_revision_recall", minimum=0.9),
                    Threshold(metric="needs_revision_recall", minimum=0.95),
                )
            },
            "two thresholds",
        ),
        ({"covers": EVERYTHING - {"unbalanced"}}, "must cover 'unbalanced'"),
        ({"covers": EVERYTHING | {"made_up"}}, "unknown category"),
        (
            {"cases": tuple(c.model_copy(update={"fast": False}) for c in _covering())},
            "the fast subset is empty",
        ),
        (
            {"cases": tuple(c.model_copy(update={"key": False}) for c in _covering())},
            "no key case",
        ),
        ({"cases": (*_covering(), _case("ok"))}, "appears twice"),
        (
            {
                "cases": (
                    *_covering()[:-1],
                    _case("ok"),
                    _case("liar", mutation="none", categories=frozenset({"unbalanced"})),
                )
            },
            "doesn't inject its categories",
        ),
        (
            {
                "cases": (
                    *(c.model_copy(update={"fast": c.id == "ok"}) for c in _covering()),
                    _case("nr", action="needs_revision", fast=True),
                )
            },
            "the fast subset has no 'failed_validation' case",
        ),
    ],
)
def test_ac2_ac4_ac7_an_incomplete_suite_is_refused_before_any_model_call(
    changes: dict[str, object], problem: str
) -> None:
    with pytest.raises(InvalidSuite, match=re.escape(problem)):
        _validate(_suite(**changes))


def test_ac7_a_threshold_of_zero_is_refused() -> None:
    with pytest.raises(ValueError):
        Threshold(metric="needs_revision_recall", minimum=0)


def test_ac2_a_screened_case_states_its_action_and_others_none() -> None:
    with pytest.raises(ValueError):
        Expected.model_validate({"stage": "screened"})
    with pytest.raises(ValueError):
        Expected.model_validate({"stage": "failed", "action": "needs_revision"})


def _codes(part: str) -> set[str]:
    return set(re.findall(r"\| `([a-z_]+)` \|", part))


def test_ac4_the_taxonomy_registry_matches_the_protected_document() -> None:
    text = (REPO / "docs" / "product" / "failure-taxonomy.md").read_text()
    failures, adversarial = text.split("## Adversarial content")
    assert _codes(failures) == FAILURE_CATEGORIES
    assert _codes(adversarial.split("## Changing")[0]) == ADVERSARIAL_CATEGORIES


def test_ac13_the_generated_eval_suites_constant_is_current() -> None:
    assert eval_suites.main(["--check"]) == 0


# --- mutations -----------------------------------------------------------------------------------


def _document() -> dict[str, object]:
    tb = generate(7).client_entities[0].trial_balances[-1]
    return trial_balance_document(
        tb, period_start=tb.as_of.replace(month=1, day=1), entity_name="E"
    )


def test_mutations_cover_every_category_and_never_change_their_input() -> None:
    assert set(cases.MUTATIONS) >= EVERYTHING
    assert cases.MUTATION_CATEGORIES["tag_breakout"] == {"prompt_injection"}
    original = _document()
    snapshot = json.dumps(original, sort_keys=True)
    for name, mutate in cases.MUTATIONS.items():
        result = mutate(original)
        assert json.dumps(original, sort_keys=True) == snapshot, name
        if name == "unreadable":
            assert isinstance(result, bytes)
            with pytest.raises(json.JSONDecodeError):
                json.loads(result)
        elif name != "none":
            assert result != original, name


def test_the_tag_breakout_mutation_tries_to_close_the_untrusted_block() -> None:
    mutated = cases.MUTATIONS["tag_breakout"](_document())
    assert isinstance(mutated, dict)
    assert "</untrusted>" in json.dumps(mutated)


# --- graders and the model judge -----------------------------------------------------------------


def test_ac5_deterministic_graders_judge_stage_action_citations_containment_and_budget() -> None:
    case = _case()
    names = ("structured_output", "citations_verified", "untrusted_contained", "within_budget")
    assert all(g.passed for g in graders.grade(names, case, _seen()))
    failing = {
        "structured_output": _seen(action="needs_revision"),
        "citations_verified": _seen(citations_verified=False),
        "untrusted_contained": _seen(contained=False),
        "within_budget": _seen(cost_usd=Decimal("1")),
    }
    for name, seen in failing.items():
        [result] = graders.grade((name,), case, seen)
        assert not result.passed, name


def test_an_errored_attempt_never_passes() -> None:
    grades = graders.grade(("within_budget",), _case(), _seen(stage="errored", error="Boom"))
    assert not all(g.passed for g in grades)


def test_ac6_the_judge_prompt_is_registered() -> None:
    assert prompt(graders.JUDGE_PROMPT).ref == "eval.judge@v0"


def _attribution() -> Attribution:
    return Attribution(TenantContext(uuid.uuid4(), "agent", "agent:x"), None, "eval.judge", None)


async def test_ac6_a_judge_without_a_calibration_record_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graders, "JUDGES", tmp_path)
    with pytest.raises(graders.UncalibratedJudge):
        await graders.judge_with_model(
            _case(), _seen(), attribution=_attribution(), tier="small", budget_usd=Decimal("0.1")
        )
    [result] = graders.grade(("model_judge",), _case(), _seen())  # the sync path refuses too
    assert not result.passed


def _record(tmp_path: Path, *, agreement: float = 0.95, tier: str = "small") -> None:
    (tmp_path / f"{graders.JUDGE_PROMPT}.yaml").write_text(
        f"prompt: {graders.JUDGE_PROMPT}\nmodel: {MODELS[tier][0]}\ntier: {tier}\n"  # type: ignore[index] -- test tiers are valid
        f"human_agreement: {agreement}\nlabels: 200\nmeasured: 2026-10-07\n"
    )


@pytest.mark.parametrize(("agreement", "tier"), [(0.5, "small"), (0.95, "medium")])
async def test_ac6_a_judge_with_a_weak_or_mismatched_record_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agreement: float, tier: str
) -> None:
    monkeypatch.setattr(graders, "JUDGES", tmp_path)
    _record(tmp_path, agreement=agreement, tier=tier)
    with pytest.raises(graders.UncalibratedJudge):
        await graders.judge_with_model(
            _case(), _seen(), attribution=_attribution(), tier="small", budget_usd=Decimal("0.1")
        )


@pytest.mark.parametrize(
    ("verdict", "passed"), [({"passed": True, "reason": "ok"}, True), (None, False)]
)
async def test_ac6_a_calibrated_judge_grades_through_the_gateway_and_its_cost_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verdict: dict[str, object] | None,
    passed: bool,
) -> None:
    monkeypatch.setattr(graders, "JUDGES", tmp_path)
    _record(tmp_path)
    calls: list[object] = []

    async def fake_call(c: object) -> GatewayResult[graders.JudgeVerdict]:
        calls.append(c)
        output = graders.JudgeVerdict.model_validate(verdict) if verdict else None
        return GatewayResult(
            "ok" if output else "escalated",
            output,
            1,
            Decimal("0.004"),
            "h",
            MODELS["small"][0],
            prompt(graders.JUDGE_PROMPT),
        )

    monkeypatch.setattr(graders, "call", fake_call)
    grade, cost = await graders.judge_with_model(
        _case(), _seen(), attribution=_attribution(), tier="small", budget_usd=Decimal("0.1")
    )
    assert (grade.grader, grade.passed, cost) == ("model_judge", passed, Decimal("0.004"))
    [made] = calls
    assert made.prompt == graders.JUDGE_PROMPT  # type: ignore[attr-defined] -- the recorded GatewayCall
    assert made.tier == "small"  # type: ignore[attr-defined] -- the recorded GatewayCall
    assert made.output_schema is graders.JudgeVerdict  # type: ignore[attr-defined] -- the recorded GatewayCall


# --- metrics, calibration and the verdict --------------------------------------------------------


def test_metrics_count_what_code_catches_as_caught_and_fail_closed_when_undefined() -> None:
    needs = _case("n", stage="failed_validation", action=None)
    ready = _case("r")
    attempts = [(needs, _seen(stage="failed_validation", action=None)), (ready, _seen())]
    assert metrics.needs_revision_recall(attempts) == 1.0
    assert metrics.ready_precision(attempts) == 1.0
    assert metrics.ready_precision([(needs, _seen(stage="failed", action=None))]) == 0.0
    missed = [(_case("n", action="needs_revision"), _seen(action="ready_for_review"))]
    assert metrics.needs_revision_recall(missed) == 0.0


def test_ac8_ece_weights_each_bands_gap_by_its_share() -> None:
    ece, bands = expected_calibration_error([(0.9, True), (0.9, True), (0.3, True), (0.3, False)])
    assert ece == pytest.approx(0.5 * 0.1 + 0.5 * 0.2)
    assert [b["band"] for b in bands] == [0.3, 0.9]


def test_ac8_ece_judges_the_models_own_answer_not_the_routed_one() -> None:
    unsure = _case("u", action="needs_revision")
    # The model said ready (wrong) at 0.3; code routed it to needs revision (right).
    seen = _seen(action="needs_revision", model_action="ready_for_review", confidence=0.3)
    result = calibrate(
        [(unsure, seen)], current_below=0.5, route="needs_revision", dangerous_minimum=0.97
    )
    assert result.ece == pytest.approx(0.3)  # accuracy 0 at confidence 0.3


def test_ac8_ac9_the_recommended_threshold_uses_the_specs_route() -> None:
    unsure = _case("u", action="needs_revision")
    attempts = [
        (unsure, _seen(action="needs_revision", model_action="ready_for_review", confidence=0.45))
    ]
    result = calibrate(attempts, current_below=0.5, route="needs_revision", dangerous_minimum=0.97)
    assert result.recommended_below == 0.5
    assert result.current_meets_threshold
    other = calibrate(
        attempts, current_below=0.5, route="ready_for_review", dangerous_minimum=0.97
    )
    assert other.recommended_below is None
    assert not calibrate(
        attempts, current_below=0.4, route="needs_revision", dangerous_minimum=0.97
    ).current_meets_threshold


def test_ac9_ac12_the_gate_names_every_reason() -> None:
    suite = _suite()
    good = calibrate([], current_below=0.5, route="needs_revision", dangerous_minimum=0.0)
    bad_calibration = calibrate(
        [(_case(), _seen(confidence=0.1))],
        current_below=0.5,
        route="needs_revision",
        dangerous_minimum=0.0,
    )
    assert reasons(suite, {"needs_revision_recall": 1.0}, good, [], None, 0) == []
    found = reasons(
        suite, {"needs_revision_recall": 0.5}, bad_calibration, [Decimal("0.2")], Decimal("0.1"), 1
    )
    assert found == [
        "threshold:needs_revision_recall",
        "calibration",
        "cost_regression",
        "case_errors",
    ]
    within = reasons(
        suite, {"needs_revision_recall": 1.0}, good, [Decimal("0.11")], Decimal("0.1"), 0
    )
    assert within == []  # 10% over the baseline is allowed (Q5)


def _ideal(suite: Suite) -> list[tuple[Case, Observation]]:
    """Every attempt of the full suite handled correctly, with honest confidences."""
    attempts: list[tuple[Case, Observation]] = []
    for case in suite.subset("full"):
        for n in range(1, (suite.repeats if case.key else 1) + 1):
            if case.expected.stage != "screened":
                attempts.append(
                    (
                        case,
                        _seen(
                            case_id=case.id,
                            attempt=n,
                            stage=case.expected.stage,
                            action=None,
                            model_action=None,
                            confidence=None,
                            citations_verified=None,
                            contained=None,
                        ),
                    )
                )
                continue
            answer = case.fake_answer
            assert answer is not None
            attempts.append(
                (
                    case,
                    _seen(
                        case_id=case.id,
                        attempt=n,
                        action=case.expected.action,
                        model_action=answer.action,
                        confidence=answer.confidence,
                    ),
                )
            )
    return attempts


def _verdict(attempts: list[tuple[Case, Observation]], *, fake: bool = True) -> Verdict:
    return judge(
        load(SUITE),
        attempts,
        fake=fake,
        aborted=False,
        baseline=None,
        current_below=0.5,
        route="needs_revision",
    )


def test_ac3_ac9_the_suites_scripted_answers_pass_the_gate() -> None:
    verdict = _verdict(_ideal(load(SUITE)))
    assert (verdict.status, verdict.reasons) == ("passed", [])


def test_ac9_negative_control_wrong_answers_fail_the_dangerous_metric() -> None:
    suite = load(SUITE)
    wrong = [
        (
            case,
            _seen(
                case_id=seen.case_id,
                attempt=seen.attempt,
                action="ready_for_review",
                model_action="ready_for_review",
                confidence=0.97,
            ),
        )
        if case.expected.action == "needs_revision"
        else (case, seen)
        for case, seen in _ideal(suite)
    ]
    verdict = _verdict(wrong)
    assert verdict.status == "failed"
    assert "threshold:needs_revision_recall" in verdict.reasons


def test_ac12_a_real_run_without_a_baseline_fails_a_fake_one_does_not() -> None:
    attempts = _ideal(load(SUITE))
    assert "cost_regression:no_baseline" in _verdict(attempts, fake=False).reasons
    assert "cost_regression:no_baseline" not in _verdict(attempts, fake=True).reasons


def test_too_many_errored_attempts_make_the_run_errored() -> None:
    attempts = [
        (case, _seen(case_id=seen.case_id, attempt=seen.attempt, stage="errored", error="Boom"))
        for case, seen in _ideal(load(SUITE))
    ]
    assert _verdict(attempts).status == "errored"


# --- the cost limit (AC-15) ----------------------------------------------------------------------


async def test_ac15_the_run_stops_before_a_case_would_pass_the_cost_limit() -> None:
    suite = _suite(cost_limit_usd=Decimal("0.05"))
    ran: list[str] = []

    async def attempt(case: Case, n: int) -> Observation:
        ran.append(case.id)
        return _seen(case_id=case.id, attempt=n, cost_usd=Decimal("0.01"))

    attempts, aborted = await runner.collect(suite, "full", Decimal("0.03"), attempt)
    assert aborted
    assert len(ran) == len(attempts) == 3  # 0.03 + 3 x 0.01 spent; a fourth would pass 0.05


async def test_ac1_key_cases_repeat_and_others_run_once() -> None:
    suite = _suite()
    counts: dict[str, int] = {}

    async def attempt(case: Case, n: int) -> Observation:
        counts[case.id] = counts.get(case.id, 0) + 1
        return _seen(case_id=case.id, attempt=n)

    _, aborted = await runner.collect(suite, "full", Decimal("0.001"), attempt)
    assert not aborted
    assert all(n == (suite.repeats if c.key else 1) for c in suite.cases for n in [counts[c.id]])


# --- summaries, signatures and publish -----------------------------------------------------------


def _summary(
    *, fake: bool = True, status: str | None = None, model: str | None = None
) -> summary.Summary:
    suite = load(SUITE)
    verdict = _verdict(_ideal(suite), fake=fake)
    now = datetime.now(UTC)
    return summary.Summary.model_validate(
        {
            "id": uuid.uuid4(),
            "agent": "evidence.screener",
            "suite_version": suite.version,
            "prompt_version": "evidence.screen@v0",
            "model": model or MODELS["small"][0],
            "tier": "small",
            "subset": "full",
            "fake": fake,
            "route": "fake",
            "seeds": {"trial_balance": 7},
            "sampling": suite.sampling,
            "status": status or verdict.status,
            "reasons": verdict.reasons,
            "metrics": verdict.metrics,
            "calibration": json.loads(json.dumps(verdict.calibration)),
            "total_cost_usd": verdict.total_cost_usd,
            "median_case_cost_usd": verdict.median_case_cost_usd,
            "started_at": now,
            "finished_at": now,
            "cases": verdict.case_rows,
        }
    )


def test_ac14_a_signature_covers_every_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(summary.SIGNING_KEY_ENV, "k")
    signed = summary.sign(_summary())
    assert summary.verified(signed)
    assert not summary.verified(signed.model_copy(update={"status": "failed"}))
    monkeypatch.setenv(summary.SIGNING_KEY_ENV, "other")
    assert not summary.verified(signed)


LOCAL = "postgresql://u:p@127.0.0.1:5432/d"


def test_ac13_publish_accepts_a_consistent_local_fake_summary() -> None:
    publish.check(_summary(), database_url=LOCAL, environment=None)


@pytest.mark.parametrize(
    ("made", "problem"),
    [
        (lambda: _summary(status="failed"), "doesn't follow"),
        (lambda: _summary(model=MODELS["large"][0]), "isn't its tier's"),
        (lambda: _summary(fake=False), "signature"),
    ],
)
def test_ac13_publish_refuses_forged_mismatched_or_unsigned_summaries(
    made: Callable[[], summary.Summary], problem: str
) -> None:
    with pytest.raises(publish.Refused, match=problem):
        publish.check(made(), database_url=LOCAL, environment=None)


def test_ac13_publish_refuses_a_remote_store_without_an_environment_and_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote = "postgresql://u:p@db.example.com:5432/d"
    with pytest.raises(publish.Refused, match="remote store"):
        publish.check(_summary(), database_url=remote, environment="staging")
    monkeypatch.setenv(summary.SIGNING_KEY_ENV, "k")
    signed = summary.sign(_summary())
    with pytest.raises(publish.Refused, match="remote store"):
        publish.check(signed, database_url=remote, environment=None)
    publish.check(signed, database_url=remote, environment="staging")


# --- the environment guard (AC-16) ---------------------------------------------------------------


class _Env:
    def __init__(self, environment: str) -> None:
        self.environment = environment


def test_ac16_evaluations_refuse_to_run_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "settings", lambda: _Env("production"))
    monkeypatch.setenv("CI", "true")  # no bypass
    with pytest.raises(runner.RefusedEnvironment):
        runner.guard()
    monkeypatch.setattr(runner, "settings", lambda: _Env("evaluation"))
    runner.guard()


@pytest.mark.parametrize("name", runner._DESTINATIONS)  # pyright: ignore[reportPrivateUsage] -- the guarded settings
def test_ac16_evaluations_refuse_a_destination_away_from_this_machine(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(runner, "settings", lambda: _Env("test"))
    for other in runner._DESTINATIONS:  # pyright: ignore[reportPrivateUsage] -- the guarded settings
        monkeypatch.delenv(other, raising=False)
    monkeypatch.setenv(name, "postgresql://u:p@db.example.com:5432/d")
    with pytest.raises(runner.RefusedEnvironment):
        runner.guard()
    monkeypatch.setenv(runner.EVALUATION_DATABASE_ENV, "postgresql://u:p@db.example.com:5432/d")
    runner.guard()  # the configured evaluation database is allowed
