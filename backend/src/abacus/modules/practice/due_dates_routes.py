"""C21 part A, the route: `GET /v1/due-dates` (K-02-T07; K-02 §4.4; rules-tables.md).

A client principal gets 404 before anything else (INV-4), then the matrix (403), then 404 with
`rules.reference_sets` off. A form with no rule in effect on the period end is 404. The inputs
are a form, a period and a place only: no TRI (§7216).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Query

from abacus.kernel._flags import RULES_REFERENCE_SETS
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.practice import due_dates
from abacus.modules.practice.due_dates_contract import (
    DueDateOut,
    DueDates,
    Jurisdiction,
    Location,
    PostponementOut,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

router = AbacusRouter(prefix="/v1/due-dates", tags=["due-dates"])


async def _gate(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("due_date")
    await authorise(ctx, "due_date.read", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, RULES_REFERENCE_SETS):
        raise NotFound(RULES_REFERENCE_SETS.name)


def _out(found: DueDates, jurisdiction: Jurisdiction) -> DueDateOut:
    postponement = None
    if found.postponement_notice_id is not None and found.postponed_to is not None:
        postponement = PostponementOut(
            notice_id=found.postponement_notice_id, postponed_to=found.postponed_to
        )
    return DueDateOut(
        form=found.form,
        tax_year=found.tax_year,
        period_end=found.period_end,
        jurisdiction=jurisdiction,
        original_due_on=found.original_due_on,
        original_rolled=found.original_rolled,
        extension_form=found.extension_form,
        extended_due_on=found.extended_due_on,
        extended_rolled=found.extended_rolled,
        postponement=postponement,
        reference_set_version_ids=list(found.reference_set_version_ids),
        inputs_hash=found.inputs_hash,
    )


@router.get("", action="due_date.read", response_model=DueDateOut)
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
    await _gate(ctx)
    location = None if state is None else Location(state=state, county=county)
    try:
        found = await due_dates.due_dates_for(form, tax_year, period_end, jurisdiction, location)
    except LookupError:
        raise NotFound("due_date") from None
    return _out(found, jurisdiction)
