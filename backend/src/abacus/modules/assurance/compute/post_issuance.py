"""Post-issuance comparison and evaluation (Q-05-T12; TASK-8718; SPEC-711 AC-15 to AC-18;
DEC-5714), pure.

The comparison sets each certified line beside its corrected amount, by code. The evaluation
measures the total difference against the materiality frozen at release: below clearly trivial or
not, and its share of overall materiality to one place (half up). The decision's options are
code's: "No action" is offered as the agent recommendation only when the difference is below
clearly trivial and no disclosure is affected; the other options are always offered; all are
reserved to the engagement partner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

ONE: Final = Decimal("0.1")
Option = Literal["no_action", "revise_and_reissue", "notify_users"]


@dataclass(frozen=True, slots=True)
class LineIn:
    line_key: str
    label: str
    as_certified: Decimal
    as_corrected: Decimal


@dataclass(frozen=True, slots=True)
class LineOut:
    line_key: str
    label: str
    as_certified: Decimal
    as_corrected: Decimal
    difference: Decimal


@dataclass(frozen=True, slots=True)
class Evaluation:
    total_difference: Decimal
    clearly_trivial: Decimal
    overall_materiality: Decimal
    share_pct: Decimal
    below_clearly_trivial: bool


def compare(lines: Sequence[LineIn]) -> list[LineOut]:
    return [
        LineOut(ln.line_key, ln.label, ln.as_certified, ln.as_corrected,
                ln.as_corrected - ln.as_certified)
        for ln in lines
    ]  # fmt: skip


def evaluate(
    difference: Decimal, *, clearly_trivial: Decimal, overall_materiality: Decimal
) -> Evaluation:
    share = (abs(difference) * 100 / overall_materiality).quantize(ONE, ROUND_HALF_UP)
    return Evaluation(
        difference, clearly_trivial, overall_materiality, share, abs(difference) < clearly_trivial
    )


@dataclass(frozen=True, slots=True)
class Options:
    options: tuple[Option, ...]
    recommended: Option | None
    reserved_to: Literal["engagement_partner"] = "engagement_partner"


def options(evaluation: Evaluation, *, disclosure_affected: bool) -> Options:
    eligible = evaluation.below_clearly_trivial and not disclosure_affected
    return Options(
        ("no_action", "revise_and_reissue", "notify_users"), "no_action" if eligible else None
    )


__all__ = ["Evaluation", "LineIn", "LineOut", "Options", "compare", "evaluate", "options"]
