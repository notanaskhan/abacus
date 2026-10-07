"""Graders (SPEC-005 AC-5, AC-6; TASK-020 design §4): each judges one attempt of one case.

Deterministic first, with no model calls: the structured output against the expected stage and
action, the citation verifier's verdict, untrusted-text containment, and budget. A model judge is
allowed only through the gateway with a registered prompt and a calibration record against human
labels (Q3): until one exists, `model_judge` refuses to grade. A grader that errors fails the
case (`grader_error`), never passes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field

from abacus.ai_gateway import (
    MODELS,
    Attribution,
    ContextBuilder,
    GatewayCall,
    Tier,
    call,
)
from abacus.kernel.classification import classified
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case


@dataclass(frozen=True)
class Grade:
    grader: str
    passed: bool
    reason: str | None = None


Grader = Callable[[Case, Observation], Grade]


def structured_output(case: Case, seen: Observation) -> Grade:
    expected = case.expected
    if seen.stage != expected.stage:
        return Grade("structured_output", False, f"stage {seen.stage} != {expected.stage}")
    if expected.stage == "screened" and seen.action != expected.action:
        return Grade("structured_output", False, f"action {seen.action} != {expected.action}")
    return Grade("structured_output", True)


def citations_verified(case: Case, seen: Observation) -> Grade:
    if seen.stage != "screened":
        return Grade("citations_verified", True, "not screened")
    return Grade("citations_verified", seen.citations_verified is True)


def untrusted_contained(case: Case, seen: Observation) -> Grade:
    if seen.stage != "screened":
        return Grade("untrusted_contained", True, "not screened")
    return Grade("untrusted_contained", seen.contained is True)


def within_budget(case: Case, seen: Observation) -> Grade:
    return Grade("within_budget", seen.cost_usd <= seen.budget_usd)


class UncalibratedJudge(RuntimeError):
    """A model judge without a calibration record against human labels can't gate (Q3)."""


JUDGES = Path(__file__).resolve().parents[4] / "evals" / "judges"
JUDGE_PROMPT = "eval.judge@v0"
MIN_AGREEMENT = 0.9  # the judge must agree with human labels this often to gate


class JudgeRecord(BaseModel):
    """`evals/judges/<prompt>.yaml`: how well this judge, on this model and tier, agreed with
    human labels, and when that was measured (AC-6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str
    model: str
    tier: Tier
    human_agreement: Annotated[float, Field(ge=0, le=1)]
    labels: Annotated[int, Field(ge=1)]
    measured: date


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: Annotated[bool, classified("internal")]
    reason: Annotated[str, Field(max_length=500), classified("internal")]


def judge_record(prompt_ref: str, tier: Tier) -> JudgeRecord:
    """The judge's calibration record; refused if missing, for another model or tier, or below
    the agreement the gate needs."""
    path = JUDGES / f"{prompt_ref}.yaml"
    if not path.exists():
        raise UncalibratedJudge(f"no calibration record for {prompt_ref} (evals/judges/)")
    record = JudgeRecord.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if record.prompt != prompt_ref or record.tier != tier or record.model != MODELS[tier][0]:
        raise UncalibratedJudge(f"{prompt_ref}'s record is for another prompt, model or tier")
    if record.human_agreement < MIN_AGREEMENT:
        raise UncalibratedJudge(f"{prompt_ref} agrees with human labels too rarely to gate")
    return record


async def judge_with_model(
    case: Case,
    seen: Observation,
    *,
    attribution: Attribution,
    tier: Tier,
    budget_usd: Decimal,
    prompt_ref: str = JUDGE_PROMPT,
) -> tuple[Grade, Decimal]:
    """A model grades the attempt, through the gateway with its own registered prompt, a pinned
    model and tier, a budget and an output schema (AC-6). Returns the grade and what it cost,
    which counts towards the run. An invalid verdict fails the case."""
    judge_record(prompt_ref, tier)
    context = (
        ContextBuilder()
        .task(
            {
                "case": case.id,
                "expected": case.expected.model_dump(mode="json"),
                "proposal": {"stage": seen.stage, "action": seen.action},
            },
            untrusted=("proposal",),
        )
        .build()
    )
    result = await call(
        GatewayCall(
            purpose="evaluation judge",
            prompt=prompt_ref,
            tier=tier,
            output_schema=JudgeVerdict,
            budget_usd=budget_usd,
            attribution=attribution,
            context=context,
            work_class="batch",
            essential=False,
            max_output_tokens=200,
        )
    )
    if result.output is None:
        return Grade("model_judge", False, "judge_invalid"), result.cost_usd
    verdict = result.output
    return Grade("model_judge", verdict.passed, None if verdict.passed else verdict.reason), (
        result.cost_usd
    )


def model_judge(case: Case, seen: Observation) -> Grade:
    """The synchronous entry refuses: a model judge runs only through `judge_with_model`, which
    the runner awaits when a suite lists `model_judge`."""
    raise UncalibratedJudge("the model judge runs through judge_with_model (the runner)")


GRADERS: Final[dict[str, Grader]] = {
    "structured_output": structured_output,
    "citations_verified": citations_verified,
    "untrusted_contained": untrusted_contained,
    "within_budget": within_budget,
    "model_judge": model_judge,
}


def grade(names: tuple[str, ...], case: Case, seen: Observation) -> list[Grade]:
    grades: list[Grade] = []
    for name in names:
        try:
            grades.append(GRADERS[name](case, seen))
        except Exception as exc:  # a grader that errors fails the case
            grades.append(Grade(name, False, f"grader_error: {type(exc).__name__}"))
    if seen.stage == "errored":
        grades.append(Grade("run", False, seen.error or "errored"))
    return grades
