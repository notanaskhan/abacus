"""C12 v1 stub: the TB hand-off into tax (T-06-T05; SPEC-702 F6, AC-27 to AC-31; DEC-66, ADR-158;
`docs/contracts/c12-tb-handoff.md`). Served by tax (ledger owns `tb_handoffs` and may not depend
on identity, BOUND-002). Screen family AUD-38 (the sheet over AUD-06), TXP-13 d and
the TXP-02 banner; C-02's CLS-12 calls the same create with `source_kind=close_lock`.

Source-agnostic: an audit's released Final TB (`audit_release`, G8), a review engagement's
release (`review_release`, OQ-4) or a locked December close (`close_lock`). The hand-off
references the source snapshot and never copies it (P-40); nothing ever posts back to the source.

Every route answers, in order: a client principal 404; `tax.tb_handoff` off 404; a create that is
not a live person's 403 (INV-1). The reads and the landing are live (T-06-T39); targets, preview
and create answer 501 until their assembly lands (T-06-T20 rest). Fixture
mode serves AUD-38 meanwhile.

Classification (ADR-031): account names and amounts are `confidential` (the TB moves into a
`tax_return` work item where TRI rules apply on the tax side, ADR-167); ids, counts and states
are `internal`. Money is `Decimal`, summed by code (ADR-050).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._flags import TAX_TB_HANDOFF
from abacus.kernel._statuses import TbHandoffStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Confidential]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]

SourceKind = Literal["audit_release", "review_release", "close_lock"]
AccountTravel = Literal["map_suggested", "send_blank", "send_as_is"]
Gate = Literal["released", "not_released", "superseded"]
# The `tb_handoff` words (C-02/T-06 status vocabulary): the first three are derived on read.
HandoffState = Literal["not_available", "needs_review", "ready", "handed_off", "superseded"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TbHandoffTargetOut(BaseModel):
    """An eligible return of the same client: metadata only, wall-safe."""

    model_config = _cfg()

    target_work_item_id: Annotated[UUID, Internal]
    return_label: Annotated[str, Field(max_length=120), Internal]  # "FY2026 Form 1120"
    tax_year: Annotated[int, Field(ge=2000, le=2100), Internal]


class TbHandoffTargetsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TbHandoffTargetOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]


class TbHandoffCountsOut(BaseModel):
    """121 mapped + 5 suggested + 2 review = 128 accounts (AUD-38 b)."""

    model_config = _cfg()

    mapped: Annotated[int, Field(ge=0), Internal]
    suggested: Annotated[int, Field(ge=0), Internal]
    review: Annotated[int, Field(ge=0), Internal]
    total: Annotated[int, Field(ge=0), Internal]


class TbHandoffReviewAccountOut(BaseModel):
    """A review account (amber) and its choice; none chosen blocks Hand off."""

    model_config = _cfg()

    account_ref: Annotated[str, Field(max_length=64), Internal]
    account_name: Annotated[str, Field(max_length=200), Confidential]
    balance: Money
    choice: Annotated[AccountTravel | None, Internal] = None
    # T-06-T06: every account names where its suggestion came from (never blank).
    source: Annotated[Literal["tb_mapper", "firm_mapping", "person"], Internal]


class TbHandoffBookIncomeOut(BaseModel):
    """Book income 3,100,000 - 750,000 = 2,350,000 (pretax, income-tax expense, net)."""

    model_config = _cfg()

    pretax: Money
    income_tax_expense: Money
    net_income: Money


class TbHandoffTaxItemOut(BaseModel):
    """A tax-relevant audit item (passed AJE-3 68,400 from the SUM)."""

    model_config = _cfg()

    key: Annotated[str, Field(max_length=60), Internal]
    label: Annotated[str, Field(max_length=200), Confidential]
    amount: Money
    included: Annotated[bool, Internal]


class TbHandoffPreviewOut(BaseModel):
    model_config = _cfg()

    source_kind: Annotated[SourceKind, Internal]
    source_snapshot_id: Annotated[UUID, Internal]
    # T-06-T06: a close_lock hand-off names the locked close it comes from.
    locked_close_id: Annotated[UUID | None, Internal] = None
    gate: Annotated[Gate, Internal]
    status: Annotated[HandoffState, Internal]
    counts: Annotated[TbHandoffCountsOut, Internal]
    review_accounts: Annotated[list[TbHandoffReviewAccountOut], Internal]
    book_income: Annotated[TbHandoffBookIncomeOut, Internal]
    schedules: Annotated[list[str], Internal] = []
    tax_items: Annotated[list[TbHandoffTaxItemOut], Internal] = []
    current_version_no: Annotated[int | None, Field(ge=1), Internal] = None
    preview_hash: Hash

    @model_validator(mode="after")
    def _close_reference(self) -> Self:
        if (self.source_kind == "close_lock") != (self.locked_close_id is not None):
            raise ValueError("a close_lock hand-off names its locked close, and only it does")
        return self


class TbHandoffAccountChoiceIn(BaseModel):
    model_config = _cfg()

    account_ref: Annotated[str, Field(min_length=1, max_length=64), Internal]
    choice: Annotated[AccountTravel, Internal]


class TbHandoffIn(BaseModel):
    model_config = _cfg()

    target_work_item_id: Annotated[UUID, Internal]
    account_choices: Annotated[list[TbHandoffAccountChoiceIn], Field(max_length=500), Internal]
    schedules: Annotated[list[str], Field(max_length=20), Internal] = []
    tax_items: Annotated[list[str], Field(max_length=50), Internal] = []
    seen_preview_hash: Hash


class TbHandoffOut(BaseModel):
    """ "Handed off to FY2026 Form 1120 · 1 tax issue created · 7 accounts for the tax team to
    map" (AUD-38 c)."""

    model_config = _cfg()

    handoff_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Field(ge=1), Internal]
    source_kind: Annotated[SourceKind, Internal]
    status: Annotated[TbHandoffStatus, Internal]
    handed_off_at: Annotated[datetime, Internal]
    tax_issues_created: Annotated[int, Field(ge=0), Internal]
    accounts_to_map: Annotated[int, Field(ge=0), Internal]
    supersedes_id: Annotated[UUID | None, Internal] = None


class TbHandoffMappingRowOut(BaseModel):
    model_config = _cfg()

    account_ref: Annotated[str, Field(max_length=64), Internal]
    account_name: Annotated[str, Field(max_length=200), Confidential]
    balance: Money
    tax_line: Annotated[str | None, Field(max_length=80), Internal] = None
    source: Annotated[Literal["tb_mapper", "firm_mapping", "person", "blank"], Internal]


class TbHandoffMappingsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TbHandoffMappingRowOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]


class TbHandoffLandingOut(BaseModel):
    """TXP-13 d and TXP-02's banner: "From FY2026 audit · Final TB · handed off Nov 9"."""

    model_config = _cfg()

    handoff_id: Annotated[UUID | None, Internal] = None
    source_kind: Annotated[SourceKind | None, Internal] = None
    locked_close_id: Annotated[UUID | None, Internal] = None
    source_label: Annotated[str | None, Field(max_length=200), Internal] = None
    handed_off_at: Annotated[datetime | None, Internal] = None
    handed_off_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    source_link_allowed: Annotated[bool, Internal] = False  # absent, never disabled
    superseded: Annotated[bool, Internal] = False
    book_income: Annotated[TbHandoffBookIncomeOut | None, Internal] = None

    @model_validator(mode="after")
    def _close_reference(self) -> Self:
        if self.source_kind == "close_lock" and self.locked_close_id is None:
            raise ValueError("a close_lock landing names its locked close")
        return self


# --- routes (each 501, one action) ------------------------------------------------------------

tb_handoff_router = AbacusRouter(prefix="/v1", tags=["tax"])
_E = "/engagements/{engagement_id}"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, TAX_TB_HANDOFF):
        raise NotFound(TAX_TB_HANDOFF.name)


@tb_handoff_router.get(
    f"{_E}/tax-handoff/targets", action="tb_handoff.preview", response_model=TbHandoffTargetsOut,
    errors=(501,),
)  # fmt: skip
async def handoff_targets_route(engagement_id: UUID, ctx: Ctx) -> TbHandoffTargetsOut:
    """Eligible returns of the same client, metadata only (T-06-T20)."""
    await _on(ctx)
    raise NotImplementedYet


@tb_handoff_router.get(
    f"{_E}/tax-handoff/preview", action="tb_handoff.preview", response_model=TbHandoffPreviewOut,
    errors=(409, 501),
)  # fmt: skip
async def handoff_preview_route(
    engagement_id: UUID, target_work_item_id: UUID, ctx: Ctx
) -> TbHandoffPreviewOut:
    """AUD-38 preview: counts, review rows, book income, tax items, gate and `preview_hash`."""
    await _on(ctx)
    raise NotImplementedYet


@tb_handoff_router.post(
    f"{_E}/tax-handoffs", action="tb_handoff.create", response_model=TbHandoffOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def handoff_create_route(
    engagement_id: UUID, body: TbHandoffIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TbHandoffOut:
    """One immutable version (C12); 409 `handoff_not_available`, `handoff_needs_review` or
    `preview_changed`. A live person's only."""
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden("tb_handoff.create", "role")
    raise NotImplementedYet


@tb_handoff_router.get(
    "/tb-handoffs/{handoff_id}", action="tb_handoff.read", response_model=TbHandoffOut,
    errors=(501,),
)  # fmt: skip
async def tb_handoff_route(handoff_id: UUID, ctx: Ctx) -> TbHandoffOut:
    """One hand-off version (T-06-T39): source members or the target return's team."""
    await _on(ctx)
    from abacus.modules.tax.tb_handoff_landing import authorise_read, issue_count

    found = cast(Any, await authorise_read(ctx, handoff_id))
    counts = found.counts
    return TbHandoffOut(
        handoff_id=found.id,
        version_no=found.version_no,
        source_kind=found.source_kind,
        status=TbHandoffStatus.SUPERSEDED if found.superseded else TbHandoffStatus.HANDED_OFF,
        handed_off_at=found.handed_off_at,
        tax_issues_created=await issue_count(ctx.tenant, found.id),
        accounts_to_map=int(counts.get("suggested", 0)) + int(counts.get("blank", 0)),
        supersedes_id=None,
    )


@tb_handoff_router.get(
    "/tb-handoffs/{handoff_id}/mappings",
    action="tb_handoff.read",
    response_model=TbHandoffMappingsOut,
    errors=(501,),
)  # fmt: skip
async def handoff_mappings_route(handoff_id: UUID, ctx: Ctx) -> TbHandoffMappingsOut:
    """The O4 128-row table (T-06-T39)."""
    await _on(ctx)
    from abacus.modules.ledger.api import tb_handoff
    from abacus.modules.tax.tb_handoff_landing import authorise_read, mapping_source

    await authorise_read(ctx, handoff_id)
    rows = await tb_handoff.choices_of(ctx.tenant, handoff_id)
    items = [
        TbHandoffMappingRowOut(
            account_ref=r.account_no,
            account_name=r.account_name,
            balance=r.balance,
            tax_line=r.tax_line_code,
            source=mapping_source(r.travel),
        )
        for r in rows
    ]
    return TbHandoffMappingsOut(items=items, total=len(items))


@tb_handoff_router.get(
    "/tax-returns/{return_id}/handoff",
    action="tax_return.read",
    response_model=TbHandoffLandingOut,
    errors=(501,),
)  # fmt: skip
async def return_handoff_route(return_id: UUID, ctx: Ctx) -> TbHandoffLandingOut:
    """The landing banner and M-1 starting point (TXP-13 d, TXP-02; T-06-T39). A return with no
    hand-off answers an empty landing (every field null)."""
    await _on(ctx)
    from abacus.modules.identity.api import authorise
    from abacus.modules.tax.overview import load_return, return_resource
    from abacus.modules.tax.tb_handoff_landing import landing

    await authorise(
        ctx, "tax_return.read", await return_resource(ctx, await load_return(ctx, return_id))
    )
    found = await landing(ctx, return_id)
    if found is None:
        return TbHandoffLandingOut()
    book = found.book_income
    before = Decimal(book.get("before_tax", "0"))
    expense = Decimal(book.get("income_tax_expense", "0"))
    return TbHandoffLandingOut(
        handoff_id=found.handoff_id,
        source_kind=cast(SourceKind, found.source_kind),
        locked_close_id=found.source_work_item_id if found.source_kind == "close_lock" else None,
        source_label=found.source_label,
        handed_off_at=found.handed_off_at,
        handed_off_by=found.handed_off_by,
        source_link_allowed=found.source_link_allowed,
        superseded=found.superseded,
        book_income=TbHandoffBookIncomeOut(
            pretax=before, income_tax_expense=expense, net_income=before - expense
        ),
    )
