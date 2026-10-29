"""C21 v1 part A, the stub: due dates and clocks (K-02-T02; K-02 §3 F2, §4.4, §4.5).
Contract: `docs/contracts/rules-tables.md`.

`practice` computes original and extended due dates from the published reference sets (due-date
rules, legal holidays, disaster postponements; ADR-300): IRC §7503 rolls a weekend or federal or
DC legal holiday to the next business day, and a covered postponement replaces the date with its
notice. Clocks are calendar days and never roll (AU-C 230 and 265 +60, FTC +30, 8879 retention
3 years after the later of the due date and the IRS received date). Code computes (ADR-050); no
date or rule is a constant here.

`GET /v1/due-dates` answers 404 for a client principal (INV-4), 403 for a principal the matrix
refuses, 404 with `rules.reference_sets` off and 501 with it on until K-02-T07. The module API
raises `NotImplementedError` until K-02-T07; its signature is frozen with C21 (S17) and T-02's
consumer contract tests import it.

The API takes form and period inputs only: no TRI (§7216). Results are `public` law applied to a
form and date, plus the version ids and an inputs hash (INV-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import RULES_REFERENCE_SETS
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
Jurisdiction = Literal["US", "DC"]
# The calendar-day clocks of I-CLOCKS (chapter 10 §10.9.3): they never roll.
ClockKind = Literal[
    "au_c_230_assembly", "au_c_265_communication", "ftc_notice", "form_8879_retention"
]


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


router = AbacusRouter(prefix="/v1/due-dates", tags=["due-dates"])


async def _stub(ctx: AuthContext) -> NoReturn:
    if ctx.client:
        raise NotFound("due_date")
    await authorise(ctx, "due_date.read", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, RULES_REFERENCE_SETS):
        raise NotFound(RULES_REFERENCE_SETS.name)
    raise NotImplementedYet


@router.get("", action="due_date.read", response_model=DueDateOut, errors=(501,))
async def practice_due_dates_route(
    ctx: Ctx,
    form: Annotated[str, Query(min_length=1, max_length=20)],
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    period_end: Annotated[date, Query()],
    jurisdiction: Annotated[Jurisdiction, Query()] = "US",
    state: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    county: Annotated[str | None, Query(max_length=60)] = None,
) -> DueDateOut:
    """Due dates with provenance: a state (and county) apply a covered postponement."""
    await _stub(ctx)


# --- C21 part A module API (frozen S17; K-02-T07 implements) -------------------------------------


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


@dataclass(frozen=True)
class ClockDue:
    kind: ClockKind
    start: date
    due_on: date


def _unbuilt() -> NoReturn:
    raise NotImplementedError("C21 part A: K-02-T07 builds the calendar engine")


async def due_dates_for(
    form: str,
    tax_year: int,
    period_end: date,
    jurisdiction: str = "US",
    location: Location | None = None,
    event_date: date | None = None,
) -> DueDates:
    """The original and extended due dates for a form and period end, from the rules in effect
    on the period end (C21 `as_of` rule). Unknown form: `LookupError`."""
    _unbuilt()


async def add_business_days(start: date, n: int, jurisdiction: str = "US") -> date:
    """`start` plus `n` business days, skipping weekends and the jurisdiction's legal holidays."""
    _unbuilt()


def clock_due(kind: ClockKind, start: date) -> ClockDue:
    """A calendar-day clock: +60 (AU-C 230, 265), +30 (FTC); never rolled."""
    _unbuilt()
