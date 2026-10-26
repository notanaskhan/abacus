"""The C9 v1 contract stub, AUD-06 family (A-02-T03; TASK-1186; SPEC-333 AC-26 to AC-29).
Contract: `docs/contracts/c09-ledger.md`; spec: SPEC-333; screen AUD-06.

The trial balance routes SPEC-309 to SPEC-311 built (`routes.py`, and the tie-out checks in
`workpapers`) stay live and ungated: their shapes are C9 v1's for list, adopt, view, candidates,
re-version, all-area leadsheets, annotations, sign-offs and checks (DEC-314). This module adds
C9 v1's remaining operations behind `ledger.tb_workpaper`: every route authorises its one
action on the engagement first (walls answer 404, independence 403), then answers 404 with the
flag off. The view by layer and the leadsheet by area are live (A-02-T10, `tb_read_model.py`,
which declares them on this router); Open in Excel (A-02-T22) and the issue link (A-02-T17)
answer 501 `not_implemented` with the flag on until their tasks.

Every amount is computed by `ledger` and sent as a decimal string (ADR-050); the browser never
sums a column. Labels and layers are C2's generated enums. No model carries a count of hidden
rows (INV-3).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import LEDGER_TB_WORKPAPER
from abacus.kernel._statuses import (
    TieOutTallyStatus,
    TrialBalanceLabelStatus,
    TrialBalanceLayerStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# `ledger_snapshots.source_kind` (migration 0149): where the snapshot came from. `other` is any
# source not in 0149's explicit list; `connector` arrives with the live ledger (A-02-T26).
SourceKind = Literal["import", "connector", "fake", "other"]
DisplayUnit = Literal["cents", "whole_dollars"]
# A line tick: a preparer's agreement to source (L1, with a citation) or a reviewer's chip (L2+).
TickKind = Literal["agreed", "reviewed"]
# An agent-drafted tick renders outlined, attributed "<person> via Agent", never with initials.
TickActor = Literal["human", "agent"]
LineFlagKind = Literal["does_not_tie"]
# What the person may do on this trial balance; the screen shows only these controls.
TbAction = Literal[
    "trial_balance.adopt",
    "trial_balance.annotate",
    "trial_balance.export",
    "tie_out_check.define",
    "sign_off.prepare",
    "sign_off.review",
    "sign_off.manager",
    "sign_off.partner",
    "sign_off.eqr",
    "ledger.pull",
    "connection.reconnect_request",
]
Money = Annotated[Decimal, classified("confidential")]


# --- the view by layer (AUD-06 a, c, d, g) -------------------------------------------------------


class TbProvenanceOut(BaseModel):
    """The caption's facts ("Imported by Simone Baptiste from a NetSuite export, Sep 11, 10:02
    AM"); the screen builds the words."""

    model_config = ConfigDict(frozen=True)

    source_kind: Annotated[SourceKind, classified("internal")]
    source: Annotated[str, classified("internal")]  # e.g. `import_netsuite`, a provider code
    pulled_at: Annotated[datetime, classified("internal")]
    adopted_by_user_id: Annotated[UUID, classified("internal")]
    adopted_by_name: Annotated[str, classified("internal")]
    adopted_at: Annotated[datetime, classified("internal")]


class TbTickOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=1, le=5), classified("internal")]
    kind: Annotated[TickKind, classified("internal")]
    actor_kind: Annotated[TickActor, classified("internal")]
    by_user_id: Annotated[
        UUID, classified("internal")
    ]  # the person, or the person the agent acted for
    by_name: Annotated[str, classified("internal")]
    initials: Annotated[str | None, classified("internal")]  # null for an agent's tick (INV-5)
    at: Annotated[datetime, classified("internal")]
    citation_id: Annotated[UUID | None, classified("internal")]
    verified: Annotated[bool, classified("internal")]  # false renders "Uncited" (INV-2)


class TbLineFlagOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[LineFlagKind, classified("internal")]
    check_id: Annotated[UUID, classified("internal")]
    issue_id: Annotated[UUID | None, classified("internal")]


class TbLayerLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    area: Annotated[str | None, classified("confidential")]
    wp_ref: Annotated[str | None, classified("internal")]
    boy: Annotated[Decimal | None, classified("confidential")]  # the prior snapshot's net
    eoy: Money  # debit minus credit
    aje: Annotated[Decimal | None, classified("confidential")]  # null on the Unadjusted layer
    rje: Annotated[Decimal | None, classified("confidential")]
    final: Annotated[Decimal | None, classified("confidential")]
    adjustment_refs: Annotated[list[str], classified("internal")] = []  # AJE-1 …
    ticks: Annotated[list[TbTickOut], classified("internal")] = []
    citation_ids: Annotated[list[UUID], classified("internal")] = []
    flags: Annotated[list[TbLineFlagOut], classified("internal")] = []


class TbGroupOut(BaseModel):
    """One group of lines with its server subtotals. Live grouping is one level (audit area)
    until A-03's grouping sets; fixture mode may render Northwind's two levels."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    label: Annotated[str, classified("confidential")]
    lines: Annotated[list[TbLayerLineOut], classified("confidential")]
    boy: Annotated[Decimal | None, classified("confidential")]
    eoy: Money


class TbNamedTotalOut(BaseModel):
    """A total the screen shows as a row (Total investments, Net assets), computed by code."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    label: Annotated[str, classified("confidential")]
    boy: Annotated[Decimal | None, classified("confidential")]
    eoy: Money


class TbLayerBalanceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    layer: Annotated[TrialBalanceLayerStatus, classified("internal")]
    debit: Money
    credit: Money
    difference: Money
    balanced: Annotated[bool, classified("internal")]


class TbChecksSummaryOut(BaseModel):
    """The check strip's tally; each check's result is `GET …/checks` (SPEC-310)."""

    model_config = ConfigDict(frozen=True)

    tie: Annotated[int, Field(ge=0), classified("internal")]
    off: Annotated[int, Field(ge=0), classified("internal")]
    pending: Annotated[int, Field(ge=0), classified("internal")]
    worst: Annotated[TieOutTallyStatus | None, classified("internal")]  # null with no checks


class TbLayerViewOut(BaseModel):
    """AUD-06's trial balance tab at one layer and version."""

    model_config = ConfigDict(frozen=True)

    trial_balance_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    label: Annotated[TrialBalanceLabelStatus, classified("internal")]
    layer: Annotated[TrialBalanceLayerStatus, classified("internal")]
    layers_available: Annotated[list[TrialBalanceLayerStatus], classified("internal")]
    display_unit: Annotated[DisplayUnit, classified("internal")]
    period_start: Annotated[date, classified("internal")]
    period_end: Annotated[date, classified("internal")]
    prior_period_end: Annotated[date | None, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    current_version_no: Annotated[int, Field(ge=1), classified("internal")]
    provenance: Annotated[TbProvenanceOut, classified("internal")]
    groups: Annotated[list[TbGroupOut], classified("confidential")]
    totals: Annotated[list[TbNamedTotalOut], classified("confidential")]
    balance: Annotated[TbLayerBalanceOut, classified("confidential")]
    checks: Annotated[TbChecksSummaryOut, classified("internal")]
    newer_snapshots: Annotated[int, Field(ge=0), classified("internal")]  # the "newer TB" banner
    allowed_actions: Annotated[list[TbAction], classified("internal")] = []


# --- the leadsheet by area (AUD-06 e) ------------------------------------------------------------


class TbLeadsheetRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]
    cy: Money
    change: Annotated[Decimal | None, classified("confidential")]
    change_pct: Annotated[Decimal | None, classified("confidential")]  # half-even to 0.1


class TbLeadsheetAreaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_balance_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    area: Annotated[str, classified("confidential")]
    unassigned: Annotated[bool, classified("internal")]  # the "Unassigned" sheet
    layer: Annotated[TrialBalanceLayerStatus, classified("internal")]
    display_unit: Annotated[DisplayUnit, classified("internal")]
    rows: Annotated[list[TbLeadsheetRowOut], classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]
    cy: Money
    change: Annotated[Decimal | None, classified("confidential")]
    change_pct: Annotated[Decimal | None, classified("confidential")]


# --- the issue link (AUD-06 c) ----------------------------------------------------------------


class TieIssueLinkIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: Annotated[UUID, classified("internal")]  # raised through C3's issues service
    seen_version: Annotated[int, Field(ge=1), classified("internal")]  # the check's version


class TieIssueLinkOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    check_id: Annotated[UUID, classified("internal")]
    issue_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    linked_by_user_id: Annotated[UUID, classified("internal")]
    linked_at: Annotated[datetime, classified("internal")]


# --- routes -------------------------------------------------------------------------------------


async def _stub(ctx: AuthContext, action: str, engagement_id: UUID) -> NoReturn:
    """Authorise the route's one action on the engagement (404 outside the tenant or behind a
    wall, 403 by role or independence), then the flag (404 off), then 501 (DEC-314, DEC-261)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, LEDGER_TB_WORKPAPER):
        raise NotFound(LEDGER_TB_WORKPAPER.name)
    raise NotImplementedYet


tb_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/trial-balances", tags=["trial balance"]
)
AreaKey = Annotated[str, Path(min_length=1, max_length=120)]


@tb_router.get(
    "/{tb_id}/export.xlsx",
    action="trial_balance.export",
    response_model=bytes,
    errors=(409, 501),
)
async def tb_export_route(
    engagement_id: UUID,
    tb_id: UUID,
    ctx: Ctx,
    layer: TrialBalanceLayerStatus = TrialBalanceLayerStatus.UNADJUSTED,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    """Open in Excel (A-02-T22): a deterministic XLSX of the layer with ticks, citations and a
    provenance footer, audited `trial_balance.exported`; formula-like text is neutralised."""
    await _stub(ctx, "trial_balance.export", engagement_id)


@tb_router.post(
    "/{tb_id}/checks/{check_id}/issue-link",
    action="tie_out_check.define",
    response_model=TieIssueLinkOut,
    status_code=201,
    errors=(409, 501),
)
async def tie_issue_link_route(
    engagement_id: UUID,
    tb_id: UUID,
    check_id: UUID,
    body: TieIssueLinkIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> TieIssueLinkOut:
    """AUD-06 c: link an issue raised through C3 to a check that does not tie (A-02-T17);
    409 `tie_out_check_stale` on a stale `seen_version`, audited `tie_out_check.issue_linked`."""
    await _stub(ctx, "tie_out_check.define", engagement_id)
