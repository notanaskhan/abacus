"""Evaluation suites (SPEC-005 §7, Q1; TASK-020 design §2).

    suite = load(Path("evals/screening/suite.yaml"))   # validated: refused before any model call

One YAML file per agent, protected (thresholds live in it, ADR-079). A suite declares its cases
(each naming a mutation of a synthetic trial balance, `cases.MUTATIONS`), its graders and metrics
(`graders.GRADERS`, `metrics.METRICS`), thresholds, the dangerous-error metric (which must have
its own threshold, ADR-081), repeats for key cases, the fast subset, the calibration tolerance
and the per-run cost limit. It must cover every failure-taxonomy and adversarial category it
declares as in scope for the agent (`covers`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus_tools.evals.taxonomy import (
    ADVERSARIAL_CATEGORIES,
    FAILURE_CATEGORIES,
    REQUIRED_COVERAGE,
)

Action = Literal["ready_for_review", "needs_revision"]
# Where correct handling ends: screened with an action, or caught by code first (control totals
# and validation: `failed_validation`; unparseable or rejected content: `failed`).
Stage = Literal["screened", "failed_validation", "failed"]


class Expected(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Stage
    action: Action | None = None

    @model_validator(mode="after")
    def _action_when_screened(self) -> Self:
        if (self.stage == "screened") != (self.action is not None):
            raise ValueError("a screened case states its action; any other stage states none")
        return self


class FakeAnswer(BaseModel):
    """What the fake model says for this case (fake runs only): the code's routing is tested."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    confidence: Annotated[float, Field(ge=0, le=1)]


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")]
    mutation: str
    categories: frozenset[str] = frozenset()
    expected: Expected
    fake_answer: FakeAnswer | None = None
    key: bool = False
    fast: bool = False


class Threshold(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str
    minimum: Annotated[float, Field(gt=0, le=1)]


class Suite(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")]
    version: Annotated[int, Field(ge=1)]
    covers: frozenset[str]
    cases: tuple[Case, ...]
    graders: tuple[str, ...]
    thresholds: tuple[Threshold, ...]
    dangerous_error: str
    repeats: Annotated[int, Field(ge=1, le=20)]
    required_pass_rate: Annotated[float, Field(gt=0, le=1)]
    calibration_tolerance: Annotated[float, Field(gt=0, le=1)]
    cost_limit_usd: Annotated[Decimal, Field(gt=0, le=100)]
    # Pinned per suite (ADR-081); recorded with every run. The gateway applies none yet: the fake
    # model ignores it, and real providers arrive with TASK-014.
    sampling: dict[str, float] = Field(default_factory=lambda: {"temperature": 0.0})

    def subset(self, which: Literal["fast", "full"]) -> tuple[Case, ...]:
        return tuple(c for c in self.cases if which == "full" or c.fast)


class InvalidSuite(ValueError):
    """The suite can't be run: refused before any model call (AC-2, AC-4, AC-7)."""


def needs_revision_class(case: Case) -> str | None:
    """The dangerous-error class a case belongs to, for `needs_revision_recall`: how evidence that
    must not be called ready is caught (by code at a stage, or by the screener). None: the case
    isn't about that error."""
    if case.expected.stage != "screened":
        return case.expected.stage
    return "screened:needs_revision" if case.expected.action == "needs_revision" else None


# Each dangerous-error metric names how to sort cases into the classes the fast subset must cover.
DANGEROUS_CLASSES: dict[str, Callable[[Case], str | None]] = {
    "needs_revision_recall": needs_revision_class,
}


def validate(
    suite: Suite,
    *,
    graders: frozenset[str],
    metrics: frozenset[str],
    mutations: Mapping[str, frozenset[str]],
) -> None:
    """Everything a suite must declare, named from the registries (`mutations` maps each mutation
    to the categories it injects), covering what its agent requires. Refused before any model
    call (AC-2, AC-4, AC-7)."""
    problems: list[str] = []
    problems.extend(f"unknown grader {name!r}" for name in suite.graders if name not in graders)
    named = [t.metric for t in suite.thresholds]
    problems.extend(
        f"metric {m!r} has two thresholds"
        for m in sorted({m for m in named if named.count(m) > 1})
    )
    for metric in set(named) | {suite.dangerous_error}:
        if metric not in metrics:
            problems.append(f"unknown metric {metric!r}")
    if suite.dangerous_error == "accuracy":
        problems.append("accuracy is never the dangerous error (ADR-081)")
    elif suite.dangerous_error not in DANGEROUS_CLASSES:
        problems.append(f"no dangerous-error classes for {suite.dangerous_error!r}")
    if suite.dangerous_error not in named:
        problems.append(f"the dangerous error {suite.dangerous_error!r} has no threshold")
    if set(named) <= {"accuracy"}:
        problems.append("accuracy alone is not a threshold (ADR-081)")
    known = FAILURE_CATEGORIES | ADVERSARIAL_CATEGORIES
    problems.extend(f"unknown category {c!r}" for c in sorted(suite.covers - known))
    required = REQUIRED_COVERAGE.get(suite.agent)
    if required is None:
        problems.append(f"no required coverage for agent {suite.agent!r}")
    else:
        problems.extend(f"must cover {c!r}" for c in sorted(required - suite.covers))
    seen: set[str] = set()
    covered: set[str] = set()
    for case in suite.cases:
        if case.id in seen:
            problems.append(f"case {case.id!r} appears twice")
        seen.add(case.id)
        injects = mutations.get(case.mutation)
        if injects is None:
            problems.append(f"case {case.id!r}: unknown mutation {case.mutation!r}")
        elif not case.categories <= injects:
            problems.append(
                f"case {case.id!r}: mutation {case.mutation!r} doesn't inject its categories"
            )
        problems.extend(
            f"case {case.id!r}: unknown category {c!r}" for c in case.categories - known
        )
        covered |= case.categories
    problems.extend(f"no case covers {c!r}" for c in sorted(suite.covers - covered))
    if not any(c.fast for c in suite.cases):
        problems.append("the fast subset is empty")
    if not any(c.key for c in suite.cases):
        problems.append("no key case: nothing is repeated")
    classify = DANGEROUS_CLASSES.get(suite.dangerous_error)
    if classify is not None:
        everywhere = {k for k in (classify(c) for c in suite.cases) if k is not None}
        fast = {k for k in (classify(c) for c in suite.cases if c.fast) if k is not None}
        problems.extend(f"the fast subset has no {k!r} case" for k in sorted(everywhere - fast))
    if problems:
        raise InvalidSuite("; ".join(problems))


def load(path: Path) -> Suite:
    raw = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    return Suite.model_validate(raw)
