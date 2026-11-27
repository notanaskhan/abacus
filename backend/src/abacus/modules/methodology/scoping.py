"""`evaluate_scoping_rules`: scoping rules evaluated by code (K-03-T18; TASK-9011; K-03 F3; SHT-03;
KNW-06; ADR-050; DEC-6017). Pure: no database, no model, no clock.

A rule is a group of conditions (`and` or `or`) over scoping answers, an effect (`show` or
`hide`) and one target (a program step, a sheet, a section, a row or a request group).

- **Answers.** One per source key: a code (`"yes"`), a set of codes (the components' performers,
  a risk area's assertions) or absent / `None` when the engagement has not answered it yet.
- **Operators.** `is` / `is_not` (on a set: the value is / is not among them), `includes` (the
  set holds the value; on a single code, equality), `is_answered`, `is_empty`. Codes compare
  case-folded.
- **Result per rule.** `and`: any false condition gives `no_change`, else any unanswered gives
  `no_answer`, else the effect (`shows` / `hides`). `or`: any true gives the effect, else any
  unanswered gives `no_answer`, else `no_change`. `is_answered` and `is_empty` are never
  unanswered.
- **Summary** (SHT-03a): the steps the shown rules show, the sheets on those steps plus the sheets
  shown directly, the targets hidden, and the requests in the shown request groups: "Shows 3
  steps · 2 sheets · hides 1 · adds 6 requests"; a zero sheet or request part is left out
  ("Shows 1 step · hides 0").
- **Conflicts.** Two rules on the same target with opposite effects conflict whatever their
  conditions (SHT-03e: the rules must be changed before Save).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

Operator = Literal["is", "is_not", "includes", "is_answered", "is_empty"]
Effect = Literal["show", "hide"]
TargetKind = Literal["step", "sheet", "section", "row", "request_group"]
Result = Literal["shows", "hides", "no_change", "no_answer"]
Answer = str | frozenset[str] | None

OPERATORS: Final[tuple[Operator, ...]] = ("is", "is_not", "includes", "is_answered", "is_empty")
TARGET_KINDS: Final[tuple[TargetKind, ...]] = ("step", "sheet", "section", "row", "request_group")


@dataclass(frozen=True)
class Condition:
    source: str
    operator: Operator
    value: str | None = None


@dataclass(frozen=True)
class Rule:
    key: str  # the rule's id, as text
    position: int
    group_op: Literal["and", "or"]
    conditions: tuple[Condition, ...]
    effect: Effect
    target_kind: TargetKind
    target_ref: str


@dataclass(frozen=True)
class Shape:
    """What the template version holds that a rule's target counts over."""

    sheets_by_step: Mapping[str, frozenset[str]]
    requests_by_group: Mapping[str, int]


@dataclass(frozen=True)
class Evaluation:
    results: tuple[tuple[Rule, Result], ...]
    shows_steps: int
    shows_sheets: int
    hides: int
    adds_requests: int

    @property
    def summary(self) -> str:
        return summary(self.shows_steps, self.shows_sheets, self.hides, self.adds_requests)


@dataclass(frozen=True)
class Conflict:
    first: int
    second: int
    target_kind: TargetKind
    target_ref: str


def _fold(answer: Answer) -> frozenset[str] | None:
    if answer is None:
        return None
    if isinstance(answer, str):
        return frozenset({answer.casefold()}) if answer.strip() else None
    folded = frozenset(a.casefold() for a in answer if a.strip())
    return folded or None


def condition_holds(condition: Condition, answers: Mapping[str, Answer]) -> bool | None:
    """True / False, or None when the source is not answered yet."""
    found = _fold(answers.get(condition.source))
    if condition.operator == "is_answered":
        return found is not None
    if condition.operator == "is_empty":
        return found is None
    if found is None:
        return None
    value = (condition.value or "").casefold()
    if condition.operator in ("is", "includes"):
        return value in found
    return value not in found  # is_not


def evaluate_rule(rule: Rule, answers: Mapping[str, Answer]) -> Result:
    held = [condition_holds(c, answers) for c in rule.conditions]
    applied: Result = "shows" if rule.effect == "show" else "hides"
    if rule.group_op == "and":
        if any(h is False for h in held):
            return "no_change"
        return "no_answer" if any(h is None for h in held) else applied
    if any(h is True for h in held):
        return applied
    return "no_answer" if any(h is None for h in held) else "no_change"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def summary(steps: int, sheets: int, hides: int, requests: int) -> str:
    parts = [f"Shows {_plural(steps, 'step')}"]
    if sheets:
        parts.append(_plural(sheets, "sheet"))
    parts.append(f"hides {hides}")
    if requests:
        parts.append(f"adds {_plural(requests, 'request')}")
    return " · ".join(parts)


def evaluate_scoping_rules(
    rules: Sequence[Rule], answers: Mapping[str, Answer], shape: Shape
) -> Evaluation:
    ordered = sorted(rules, key=lambda r: (r.position, r.key))
    results: tuple[tuple[Rule, Result], ...] = tuple(
        (r, evaluate_rule(r, answers)) for r in ordered
    )
    shown: dict[TargetKind, set[str]] = {k: set() for k in TARGET_KINDS}
    hidden: set[tuple[TargetKind, str]] = set()
    for rule, result in results:
        if result == "shows":
            shown[rule.target_kind].add(rule.target_ref)
        elif result == "hides":
            hidden.add((rule.target_kind, rule.target_ref))
    sheets = set(shown["sheet"])
    for step in shown["step"]:
        sheets |= shape.sheets_by_step.get(step, frozenset())
    sheets -= {ref for kind, ref in hidden if kind == "sheet"}
    requests = sum(shape.requests_by_group.get(g, 0) for g in shown["request_group"])
    return Evaluation(
        results,
        len(shown["step"] - {ref for kind, ref in hidden if kind == "step"}),
        len(sheets),
        len(hidden),
        requests,
    )


def conflicts(rules: Iterable[Rule]) -> list[Conflict]:
    """Each pair of rules showing and hiding the same target, by position."""
    by_target: dict[tuple[TargetKind, str], list[Rule]] = {}
    for rule in rules:
        by_target.setdefault((rule.target_kind, rule.target_ref), []).append(rule)
    found: list[Conflict] = []
    for (kind, ref), group in sorted(by_target.items()):
        shows = sorted(r.position for r in group if r.effect == "show")
        hides = sorted(r.position for r in group if r.effect == "hide")
        for s in shows:
            for h in hides:
                found.append(Conflict(min(s, h), max(s, h), kind, ref))
    return sorted(found, key=lambda c: (c.first, c.second))


__all__ = [
    "OPERATORS",
    "TARGET_KINDS",
    "Answer",
    "Condition",
    "Conflict",
    "Evaluation",
    "Rule",
    "Shape",
    "condition_holds",
    "conflicts",
    "evaluate_rule",
    "evaluate_scoping_rules",
    "summary",
]
