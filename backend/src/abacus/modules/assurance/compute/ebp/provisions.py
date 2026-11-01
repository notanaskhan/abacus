"""The EBP provisions registry and comparison (A-05-T13; A-05 §3 F2; DEC-1957). Pure.

The twenty provisions EBP-02 reviews (AU-C 703: the provisions that affect the statements), in
the design's order, each on its row of the EBP-02 paper (B: the plan's election, C: the plan
document reference). Two are governed by the 2024 amendment from Jan 1, 2025 (long-term part-time
and catch-up), so a version read from the pre-amendment adoption agreement holds eighteen.

Code, not the model, compares the documents: `normalise` folds case, spacing, punctuation and the
common spelled forms ("first of the month following" = "first of month following"), and
`conflicts` names each provision whose SPD wording differs from the governing document's after
normalising; `governing` picks the amendment over the adoption agreement from its effective date.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

ENGINE_NAME: Final = "ebp_provisions"
ENGINE_VERSION: Final = "1"
Source = Literal["adoption_agreement", "amendment", "spd"]


@dataclass(frozen=True)
class Provision:
    key: str
    label: str
    row: int  # the EBP-02 paper row: B<row> the election, C<row> the reference
    amendment_governed: bool = False

    @property
    def value_cell(self) -> str:
        return f"B{self.row}"

    @property
    def reference_cell(self) -> str:
        return f"C{self.row}"


_KEYS: Final = (
    ("plan_year", "Plan year", False),
    ("minimum_age", "Minimum age", False),
    ("service_requirement", "Service requirement", False),
    ("entry_dates", "Entry dates", False),
    ("excluded_classes", "Excluded classes", False),
    ("long_term_part_time", "Long-term part-time", True),
    ("compensation", "Compensation", False),
    ("auto_enrollment", "Auto-enrollment", False),
    ("default_deferral_rate", "Default deferral rate", False),
    ("auto_escalation", "Auto-escalation", False),
    ("qdia", "QDIA", False),
    ("roth_deferrals", "Roth deferrals", False),
    ("catch_up", "Catch-up", True),
    ("safe_harbor_match", "Safe harbor match", False),
    ("match_vesting", "Match vesting", False),
    ("forfeitures", "Forfeitures", False),
    ("loans", "Loans", False),
    ("in_service_withdrawals", "In-service withdrawals", False),
    ("hardship", "Hardship", False),
    ("plan_expenses", "Plan expenses", False),
)
PROVISIONS: Final[tuple[Provision, ...]] = tuple(
    Provision(key, label, row, governed) for row, (key, label, governed) in enumerate(_KEYS, 2)
)
BY_KEY: Final = {p.key: p for p in PROVISIONS}
BY_CELL: Final = {p.value_cell: p for p in PROVISIONS} | {p.reference_cell: p for p in PROVISIONS}

_SPELLED: Final = (
    (re.compile(r"\bthe\b"), ""),
    (re.compile(r"\bpercent\b"), "%"),
    (re.compile(r"\bfirst day of\b"), "first of"),
    (re.compile(r"\bmonths\b"), "month"),
    (re.compile(r"\byears\b"), "year"),
)
_PUNCT: Final = re.compile(r"[^\w%§.]+")


def normalise(text: str) -> str:
    """Comparable wording: NFKC, case-folded, articles and spelled forms folded, punctuation and
    spacing collapsed. Never used to decide alone: a conflict is shown to a person."""
    out = unicodedata.normalize("NFKC", text).casefold()
    for pattern, replacement in _SPELLED:
        out = pattern.sub(replacement, out)
    return " ".join(_PUNCT.sub(" ", out).split())


def provisions_for(*, amendment_in_force: bool) -> tuple[Provision, ...]:
    """The rows a plan review holds: all twenty with the amendment, eighteen without it."""
    if amendment_in_force:
        return PROVISIONS
    return tuple(p for p in PROVISIONS if not p.amendment_governed)


def amendment_governs(effective_on: date | None, plan_year_end: date) -> bool:
    """The amendment governs the plan year when it took effect on or before its end."""
    return effective_on is not None and effective_on <= plan_year_end


def governing(
    key: str,
    values: Mapping[Source, str | None],
    *,
    amendment_effective_on: date | None,
    plan_year_end: date,
) -> Source | None:
    """Which document's wording governs a provision: the amendment from its effective date for
    the provisions it changes, else the adoption agreement; never the SPD."""
    provision = BY_KEY[key]
    if (
        provision.amendment_governed
        and values.get("amendment")
        and amendment_governs(amendment_effective_on, plan_year_end)
    ):
        return "amendment"
    return "adoption_agreement" if values.get("adoption_agreement") else None


@dataclass(frozen=True)
class Conflict:
    key: str
    governing: Source
    governing_value: str
    spd_value: str


def conflicts(
    by_key: Mapping[str, Mapping[Source, str | None]],
    *,
    amendment_effective_on: date | None,
    plan_year_end: date,
) -> list[Conflict]:
    """Each provision whose SPD wording differs from its governing document's, in row order."""
    out: list[Conflict] = []
    for provision in PROVISIONS:
        values = by_key.get(provision.key)
        if values is None or not values.get("spd"):
            continue
        source = governing(
            provision.key,
            values,
            amendment_effective_on=amendment_effective_on,
            plan_year_end=plan_year_end,
        )
        if source is None:
            continue
        governed = values[source] or ""
        spd = values["spd"] or ""
        if normalise(governed) != normalise(spd):
            out.append(Conflict(provision.key, source, governed, spd))
    return out
