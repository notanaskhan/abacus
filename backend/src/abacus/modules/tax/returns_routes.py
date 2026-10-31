"""Tax returns v1, the routes (T-02-T01 stubs; T-02-T09 the board; tax-returns.md).

Every route answers 404 for a client principal (INV-4), then the matrix (403), then 404 with
`tax.returns_v1` off. The board's list, summary and bulk assignment are live (T-02-T09); the
record, overview, intake, single assignment and transitions answer 501 until T-02-T13; the
intake is live from T-02-T18 (`intake.py`).
"""

from __future__ import annotations

from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query

from abacus.kernel._flags import TAX_RETURNS_V1
from abacus.kernel._statuses import ReturnStatus
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.tax import board, intake, overview
from abacus.modules.tax.returns_contract import (
    AssignmentIn,
    BulkAssignIn,
    BulkAssignOut,
    Form,
    ReviewLevel,
    TaxReturnIntakeOut,
    TaxReturnOverviewOut,
    TaxReturnRecordOut,
    TaxReturnRowOut,
    TaxReturnSummaryOut,
    TransitionIn,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
ReturnId = Annotated[UUID, Path()]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]

returns_router = AbacusRouter(prefix="/v1/tax-returns", tags=["tax-returns"])


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("tax_return")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, TAX_RETURNS_V1):
        raise NotFound(TAX_RETURNS_V1.name)


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """Until T-02-T13: the gate, then 501."""
    await _gate(ctx, action)
    raise NotImplementedYet


@returns_router.get(
    "", action="tax_return.read_metadata", response_model=ListPage[TaxReturnRowOut]
)
async def list_returns_route(
    ctx: Ctx,
    tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    status: Annotated[list[ReturnStatus] | None, Query()] = None,
    review_level: Annotated[ReviewLevel | None, Query()] = None,
    form: Annotated[list[Form] | None, Query()] = None,
    office: Annotated[list[UUID] | None, Query()] = None,
    partner: Annotated[UUID | None, Query()] = None,
    preparer: Annotated[UUID | None, Query()] = None,
    due_within_days: Annotated[int | None, Query(ge=0, le=366)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    group_by: Annotated[Literal["office"] | None, Query()] = None,
    sort: Annotated[Literal["extended_due", "client"] | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ListPage[TaxReturnRowOut]:
    """TAX-01's rows, wall-safe; one page (a season's board fits; `cursor` is reserved)."""
    await _gate(ctx, "tax_return.read_metadata")
    items = await board.list_returns(
        ctx,
        board.Filters(
            tax_year=tax_year,
            status=frozenset(status or ()),
            review_level=review_level,
            form=frozenset(form or ()),
            office=frozenset(office or ()),
            partner=partner,
            preparer=preparer,
            due_within_days=due_within_days,
            q=q,
            group_by_office=group_by == "office",
            sort=sort or "extended_due",
        ),
    )
    return ListPage[TaxReturnRowOut](items=items, total=len(items))


@returns_router.get(
    "/summary", action="tax_return.read_metadata", response_model=TaxReturnSummaryOut
)
async def returns_summary_route(
    ctx: Ctx, tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None
) -> TaxReturnSummaryOut:
    """TAX-01's tiles: per status, open and done, extended, office totals (wall-safe)."""
    await _gate(ctx, "tax_return.read_metadata")
    return await board.summary(ctx, tax_year)


@returns_router.post(":bulk-assign", action="tax_return.assign", response_model=BulkAssignOut)
async def bulk_assign_route(
    body: BulkAssignIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> BulkAssignOut:
    """The selection bar's Assign preparer: assigned and refused counts, never a reason."""
    await _gate(ctx, "tax_return.assign")

    async def run() -> tuple[int, dict[str, object]]:
        out = await board.bulk_assign(ctx, body.return_ids, body.role, body.user_id)
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="tax_return.bulk_assign",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return BulkAssignOut.model_validate(stored.body)


@returns_router.get(
    "/{return_id}",
    action="tax_return.read_metadata",
    response_model=TaxReturnRecordOut,
)
async def return_record_route(return_id: ReturnId, ctx: Ctx) -> TaxReturnRecordOut:
    """TAX-02's record: the row, the engine id, the policy pin, the tabs (T-02-T13)."""
    await _gate(ctx, "tax_return.read_metadata")
    return await overview.record(ctx, return_id)


@returns_router.get(
    "/{return_id}/overview",
    action="tax_return.read_metadata",
    response_model=TaxReturnOverviewOut,
)
async def return_overview_route(return_id: ReturnId, ctx: Ctx) -> TaxReturnOverviewOut:
    """TAX-02's overview (T-02-T13): metadata for every reader of the return; the engine figures
    only with `tax_return.read` (absent, not masked, otherwise)."""
    await _gate(ctx, "tax_return.read_metadata")
    return await overview.overview(ctx, return_id)


@returns_router.get(
    "/{return_id}/intake",
    action="tax_return.read",
    response_model=TaxReturnIntakeOut,
    errors=(),
)
async def return_intake_route(return_id: ReturnId, ctx: Ctx) -> TaxReturnIntakeOut:
    """TAX-03's intake (T-02-T18): binder, requests, waiting files, questions, hand-offs."""
    await _gate(ctx, "tax_return.read")
    return await intake.intake(ctx, return_id)


@returns_router.post(
    "/{return_id}/assignments",
    action="tax_return.assign",
    response_model=TaxReturnRecordOut,
    errors=(409, 501),
)
async def return_assign_route(
    return_id: ReturnId, body: AssignmentIn, ctx: Ctx
) -> TaxReturnRecordOut:
    await _stub(ctx, "tax_return.assign")


@returns_router.post(
    "/{return_id}/transitions",
    action="tax_return.status_change",
    response_model=TaxReturnRecordOut,
    errors=(409,),
)
async def transition_route(
    return_id: ReturnId, body: TransitionIn, ctx: Ctx
) -> TaxReturnRecordOut:
    """`start_preparation` or `start_review` at the version seen (T-02-T13). 409
    `transition_refused`, `stale_version`."""
    await _gate(ctx, "tax_return.status_change")
    return await overview.transition(ctx, return_id, body.event, body.seen_version)
