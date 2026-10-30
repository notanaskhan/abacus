"""C21 v1 part A, the contract: due dates and clocks (K-02-T02; K-02 §3 F2, §4.4, §4.5).
Contract: `docs/contracts/rules-tables.md`.

`practice` computes original and extended due dates from the published reference sets (due-date
rules, legal holidays, disaster postponements; ADR-300): IRC §7503 rolls a weekend or federal or
DC legal holiday to the next business day, and a covered postponement replaces the date with its
notice. Clocks are calendar days and never roll (AU-C 230 and 265 +60, FTC +30, 8879 retention
3 years after the later of the due date and the IRS received date). Code computes (ADR-050); no
date or rule is a constant here.

The route lives in `due_dates_routes.py`, the service in `due_dates.py` and the date math in
`compute/calendar.py` (K-02-T07). The module API's signature is frozen with C21 (S17) and T-02's
consumer contract tests import it.

The API takes form and period inputs only: no TRI (§7216). Results are `public` law applied to a
form and date, plus the version ids and an inputs hash (INV-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.practice.compute.calendar import ClockKind

Jurisdiction = Literal["US", "DC"]


class PostponementOut(BaseModel):
    """The disaster postponement that moved a date, by its notice."""

    model_config = ConfigDict(frozen=True)

    notice_id: Annotated[str, classified("public")]
    postponed_to: Annotated[date, classified("public")]


class DueDateOut(BaseModel):
    """A return's original and extended due dates, with the rules that produced them."""

    model_config = ConfigDict(frozen=True)

    form: Annotated[str, classified("public")]
    tax_year: Annotated[int, classified("public")]
    period_end: Annotated[date, classified("public")]
    jurisdiction: Annotated[Jurisdiction, classified("public")]
    original_due_on: Annotated[date, classified("public")]
    # Moved off a weekend or legal holiday (IRC §7503).
    original_rolled: Annotated[bool, classified("public")]
    extension_form: Annotated[str | None, classified("public")]
    extended_due_on: Annotated[date | None, classified("public")]
    extended_rolled: Annotated[bool, classified("public")]
    postponement: Annotated[PostponementOut | None, classified("public")]
    # INV-2: the reference-set versions read, and a hash of the inputs.
    reference_set_version_ids: Annotated[list[UUID], classified("internal")]
    inputs_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$"), classified("internal")]


# --- C21 part A module API results (frozen S17; `due_dates.py` builds them) ---------------------


@dataclass(frozen=True)
class Location:
    """Where the taxpayer is, for disaster postponements."""

    state: str
    county: str | None = None


@dataclass(frozen=True)
class DueDates:
    form: str
    tax_year: int
    period_end: date
    jurisdiction: str
    original_due_on: date
    original_rolled: bool
    extension_form: str | None
    extended_due_on: date | None
    extended_rolled: bool
    postponement_notice_id: str | None
    reference_set_version_ids: tuple[UUID, ...]
    inputs_hash: str
    # Additive (K-02-T07): the date the named postponement moved the return to.
    postponed_to: date | None = None
    # Additive (T-02-T10): the rule as the Due popover reads it, original and extended.
    rule_text: str | None = None
    extended_rule_text: str | None = None


@dataclass(frozen=True)
class ClockDue:
    kind: ClockKind
    start: date
    due_on: date
