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

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus_tools.evals.taxonomy import ADVERSARIAL_CATEGORIES, FAILURE_CATEGORIES

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
    minimum: Annotated[float, Field(ge=0, le=1)]


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

    def subset(self, which: Literal["fast", "full"]) -> tuple[Case, ...]:
        return tuple(c for c in self.cases if which == "full" or c.fast)


class InvalidSuite(ValueError):
    """The suite can't be run: refused before any model call (AC-2, AC-4, AC-7)."""


def validate(
    suite: Suite, *, graders: frozenset[str], metrics: frozenset[str], mutations: frozenset[str]
) -> None:
    """Everything a suite must declare, named from the registries, covering its categories."""
    problems: list[str] = []
    for name in suite.graders:
        if name not in graders:
            problems.append(f"unknown grader {name!r}")
    named = {t.metric for t in suite.thresholds}
    for metric in named | {suite.dangerous_error}:
        if metric not in metrics:
            problems.append(f"unknown metric {metric!r}")
    if suite.dangerous_error not in named:
        problems.append(f"the dangerous error {suite.dangerous_error!r} has no threshold")
    if named <= {"accuracy"}:
        problems.append("accuracy alone is not a threshold (ADR-081)")
    known = FAILURE_CATEGORIES | ADVERSARIAL_CATEGORIES
    for category in suite.covers - known:
        problems.append(f"unknown category {category!r}")
    seen: set[str] = set()
    for case in suite.cases:
        if case.id in seen:
            problems.append(f"case {case.id!r} appears twice")
        seen.add(case.id)
        if case.mutation not in mutations:
            problems.append(f"case {case.id!r}: unknown mutation {case.mutation!r}")
        problems.extend(
            f"case {case.id!r}: unknown category {c!r}" for c in case.categories - known
        )
    covered: set[str] = set()
    for case in suite.cases:
        covered |= case.categories
    problems.extend(f"no case covers {c!r}" for c in sorted(suite.covers - covered))
    if not any(c.fast for c in suite.cases):
        problems.append("the fast subset is empty")
    if problems:
        raise InvalidSuite("; ".join(problems))


def load(path: Path) -> Suite:
    raw = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    return Suite.model_validate(raw)
