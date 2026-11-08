"""Form 5500 tie-out (A-05-T54; A-05 §4.4 `form5500`; EBP-07): pure functions.

Each Schedule H line's draft amount against the financial statements' amount for the captions the
firm maps to it: a zero difference ties; a difference equal to the documented basis differences
for that line is a reconciling item (it needs its note, Note 8 for Northwind's 48,600 receivable =
15,060 + 33,540); anything else is inconsistent. Part IV 4a ("late deposits?") must agree with the
late remittances on the late-deposit finding (EBP-04): "No" with any late deposit, or "Yes" with
another amount, is inconsistent. Net assets tie as a sum (16,812,400 = 14,228,500 + 2,583,900).
Decimal only; nothing here reads a model's output.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

ENGINE_NAME: Final = "ebp_form5500"
ENGINE_VERSION: Final = "1"
_ZERO: Final = Decimal(0)
Classification = Literal["tie", "reconciling_item", "inconsistent"]
PartIvResult = Literal["consistent", "inconsistent"]


@dataclass(frozen=True)
class LineTie:
    line_code: str
    fs_amount: Decimal | None
    f5500_amount: Decimal | None
    difference: Decimal | None
    classification: Classification
    inputs_hash: str


def inputs_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def classify(
    line_code: str,
    fs_amount: Decimal | None,
    f5500_amount: Decimal | None,
    basis_differences: Sequence[Decimal] = (),
) -> LineTie:
    """A missing side is inconsistent (nothing to tie); signs follow FS minus Form 5500."""
    digest = inputs_hash([line_code, fs_amount, f5500_amount, sorted(basis_differences)])
    if fs_amount is None or f5500_amount is None:
        return LineTie(line_code, fs_amount, f5500_amount, None, "inconsistent", digest)
    difference = fs_amount - f5500_amount
    if difference == _ZERO:
        kind: Classification = "tie"
    elif basis_differences and sum(basis_differences, _ZERO) == difference:
        kind = "reconciling_item"
    else:
        kind = "inconsistent"
    return LineTie(line_code, fs_amount, f5500_amount, difference, kind, digest)


def amounts_by_line(
    fs_by_caption: Mapping[str, Decimal], caption_to_line: Mapping[str, str]
) -> dict[str, Decimal]:
    """The FS amount per Schedule H line: the sum of the captions the firm maps to it."""
    out: dict[str, Decimal] = {}
    for caption, amount in fs_by_caption.items():
        line = caption_to_line.get(caption)
        if line is not None:
            out[line] = out.get(line, _ZERO) + amount
    return out


def part_iv_4a(
    draft_answer: str | None, amount: Decimal | None, late_total: Decimal
) -> PartIvResult:
    """4a: late deposits of participant contributions (EBP-04's finding)."""
    if late_total > _ZERO:
        return "consistent" if draft_answer == "yes" and amount == late_total else "inconsistent"
    return "consistent" if draft_answer in ("no", "na") else "inconsistent"


def sums_to(total: Decimal, parts: Sequence[Decimal]) -> bool:
    return sum(parts, _ZERO) == total


# --- Schedule H line 4i (A-05-T59; DEC-2816) -----------------------------------------------------
# The schedule of assets held at end of year, from the trust's holdings: column (a) marks a party
# in interest ("*"), column (d) cost is omitted ("**") for participant-directed investments (29 CFR
# 2520.103-11 permits it), and the total must equal the draft's investments plus loans. Ordering
# is the caller's (the trust report's). Code adds the column; no model reads a figure.


@dataclass(frozen=True)
class HeldAsset:
    identity: str
    description: str
    current_value: Decimal
    cost: Decimal | None
    party_in_interest: bool
    participant_directed: bool


@dataclass(frozen=True)
class Schedule4iRow:
    mark: Literal["*", ""]
    identity: str
    description: str
    cost: Decimal | None
    cost_omitted: bool
    current_value: Decimal


@dataclass(frozen=True)
class Schedule4i:
    rows: tuple[Schedule4iRow, ...]
    total: Decimal
    ties: bool
    inputs_hash: str


def schedule_4i(assets: Sequence[HeldAsset], draft_total: Decimal | None) -> Schedule4i:
    """The 4i rows and their total; `ties` when the total equals the draft's own figure."""
    rows = tuple(
        Schedule4iRow(
            mark="*" if a.party_in_interest else "",
            identity=a.identity,
            description=a.description,
            cost=None if a.participant_directed else a.cost,
            cost_omitted=a.participant_directed,
            current_value=a.current_value,
        )
        for a in assets
    )
    total = sum((r.current_value for r in rows), _ZERO)
    payload = [[r.identity, str(r.current_value), r.mark, r.cost_omitted] for r in rows] + [
        str(draft_total)
    ]
    return Schedule4i(rows, total, draft_total is not None and total == draft_total,
                      inputs_hash(payload))  # fmt: skip
