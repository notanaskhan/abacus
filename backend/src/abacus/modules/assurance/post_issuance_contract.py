"""Post-issuance v1 stub (Q-05-T03; SPEC-711 AC-15 to AC-18; the post-issuance section of
`docs/contracts/audit-completion.md`). Screen AUD-30: cases on an archived audit (AU-C 560,
AU-C 585, reissuance requests), the code's comparison and evaluation, the analysis and the EP's
decision. The case service (`assurance/post_issuance.py`, Q-05-T12) writes under the locked work
item's `post_issuance` exception kind; this stub writes nothing.

Every route answers, in order: a client principal 404 (no portal route; INV-4); the
`audit.post_issuance` flag off 404; a human-only route refuses an agent, the platform or a
support session 403 (INV-1); then 501 until its build task.

Classification (ADR-031): figures from the client's records and the case description are
`confidential` (attest work, not TRI); ids, refs, codes and states are `internal`. The comparison
and evaluation are computed by code (ADR-050); the agent never decides (INV-1).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDIT_POST_ISSUANCE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Confidential]

CaseType = Literal["subsequently_discovered_facts", "omitted_procedure", "reissuance_request"]
CaseStatus = Literal["under_evaluation", "concluded_no_action", "reissue_in_progress", "concluded"]
Source = Literal["inbox_evidence", "inspection_finding", "other"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class PostIssuanceComparisonLineOut(BaseModel):
    model_config = _cfg()

    line_key: Annotated[str, Field(max_length=40), Internal]
    label: Annotated[str, Field(max_length=200), Confidential]
    as_certified: Money
    as_corrected: Money
    difference: Money
    as_certified_citation_id: Annotated[UUID | None, Internal] = None
    as_corrected_citation_id: Annotated[UUID | None, Internal] = None


class PostIssuanceEvaluationOut(BaseModel):
    """AUD-30 a (AC-15): (12,250) below clearly trivial 12,610; 4.9% of 252,200."""

    model_config = _cfg()

    total_difference: Money
    clearly_trivial: Money
    overall_materiality: Money
    share_pct: Annotated[Decimal, Field(max_digits=7, decimal_places=1), Internal]
    materiality_version_id: Annotated[UUID, Internal]
    below_clearly_trivial: Annotated[bool, Internal]


class PostIssuanceCaseOut(BaseModel):
    model_config = _cfg()

    case_id: Annotated[UUID, Internal]
    ref: Annotated[str, Field(max_length=10), Internal]
    type: Annotated[CaseType, Internal]
    standard: Annotated[Literal["au_c_560", "au_c_585"] | None, Internal] = None
    source_kind: Annotated[Source, Internal]
    received_at: Annotated[datetime, Internal]
    description: Annotated[str, Field(max_length=2000), Confidential]
    status: Annotated[CaseStatus, Internal]
    comparison: Annotated[list[PostIssuanceComparisonLineOut], Internal] = []
    evaluation: PostIssuanceEvaluationOut | None = None
    analysis_run_id: Annotated[UUID | None, Internal] = None
    decision_card_id: Annotated[UUID | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class PostIssuanceCaseListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[PostIssuanceCaseOut], Internal]
    archive_locked_at: Annotated[datetime | None, Internal] = None


class PostIssuanceCaseIn(BaseModel):
    """AUD-30 f: type, source, description."""

    model_config = _cfg()

    type: Annotated[CaseType, Internal]
    source_kind: Annotated[Source, Internal]
    source_evidence_version_id: Annotated[UUID | None, Internal] = None
    description: Annotated[str, Field(min_length=1, max_length=2000), Confidential]


class PostIssuanceRunOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    started_at: Annotated[datetime, Internal]


class PostIssuanceReissueOut(BaseModel):
    model_config = _cfg()

    case_id: Annotated[UUID, Internal]
    report_release_id: Annotated[UUID, Internal]
    href: Annotated[str, Field(max_length=200), Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

post_issuance_router = AbacusRouter(prefix="/v1", tags=["assurance"])
_C = "/audits/{work_item_id}/post-issuance/cases"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, AUDIT_POST_ISSUANCE):
        raise NotFound(AUDIT_POST_ISSUANCE.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@post_issuance_router.get(
    _C, action="post_issuance.read", response_model=PostIssuanceCaseListOut, errors=(501,)
)
async def post_issuance_cases_route(work_item_id: UUID, ctx: Ctx) -> PostIssuanceCaseListOut:
    await _on(ctx)
    raise NotImplementedYet


@post_issuance_router.get(
    f"{_C}/{{case_id}}",
    action="post_issuance.read",
    response_model=PostIssuanceCaseOut,
    errors=(501,),
)
async def post_issuance_case_route(
    work_item_id: UUID, case_id: UUID, ctx: Ctx
) -> PostIssuanceCaseOut:
    await _on(ctx)
    raise NotImplementedYet


@post_issuance_router.post(
    _C,
    action="post_issuance.create",
    response_model=PostIssuanceCaseOut,
    status_code=201,
    errors=(409, 501),
)
async def post_issuance_case_create_route(
    work_item_id: UUID, body: PostIssuanceCaseIn, ctx: Ctx, key: IdempotencyKey
) -> PostIssuanceCaseOut:
    """Only on an archived audit; the locked documentation is never edited (AC-17)."""
    await _human(ctx, "post_issuance.create")
    raise NotImplementedYet


@post_issuance_router.post(
    f"{_C}/{{case_id}}/analysis",
    action="post_issuance.analyse",
    response_model=PostIssuanceRunOut,
    status_code=202,
    errors=(409, 501),
)
async def post_issuance_analysis_route(
    work_item_id: UUID, case_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> PostIssuanceRunOut:
    """409 `comparison_unavailable` (DV-9); the analysis ends with the not-decided sentence."""
    await _human(ctx, "post_issuance.analyse")
    raise NotImplementedYet


@post_issuance_router.post(
    f"{_C}/{{case_id}}/reopen-for-reissue",
    action="post_issuance.reissue",
    response_model=PostIssuanceReissueOut,
    errors=(409, 501),
)
async def post_issuance_reissue_route(
    work_item_id: UUID, case_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> PostIssuanceReissueOut:
    """The EP, fresh MFA; opens AUD-23 g through A-07's release path (AC-18)."""
    await _human(ctx, "post_issuance.reissue")
    raise NotImplementedYet
