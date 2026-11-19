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
from typing import Annotated, Literal, cast
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
DecisionOption = Literal["no_action", "revise_and_reissue", "notify_users"]
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
    # S51 partials (DEC-5724): the EP decides on the case row; the options are code's and the
    # agent recommendation is a tag on one of them, never a decision.
    source_evidence_version_id: Annotated[UUID | None, Internal] = None
    disclosure_affected: Annotated[bool | None, Internal] = None
    options: Annotated[list[DecisionOption], Internal] = []
    recommended_option: Annotated[DecisionOption | None, Internal] = None
    decision: Annotated[DecisionOption | None, Internal] = None
    decided_by_user_id: Annotated[UUID | None, Internal] = None
    decided_at: Annotated[datetime | None, Internal] = None


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


class PostIssuanceComparisonIn(BaseModel):
    """DV-9: the corrected figures by certified line key (the parser's output, or attached when it
    cannot match); the code compares and evaluates."""

    model_config = _cfg()

    corrected: Annotated[
        dict[Annotated[str, Field(pattern=r"^[a-z0-9_.-]{1,80}$")], Money],
        Field(min_length=1, max_length=200),
    ]
    disclosure_affected: Annotated[bool, Internal] = False


class PostIssuanceDecisionIn(BaseModel):
    model_config = _cfg()

    decision: Annotated[DecisionOption, Internal]
    rationale: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


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


_TYPE_OUT: dict[str, CaseType] = {
    "subsequent_fact": "subsequently_discovered_facts",
    "omitted_procedure": "omitted_procedure",
    "reissuance_request": "reissuance_request",
}
_TYPE_IN: dict[str, str] = {v: k for k, v in _TYPE_OUT.items()}


def _status(found: object) -> CaseStatus:
    """The table's lifecycle in AUD-30's words: decided cases by their decision."""
    from abacus.modules.assurance.post_issuance import Case

    c = cast(Case, found)
    if c.status != "decided":
        return "under_evaluation"
    return {"no_action": "concluded_no_action", "revise_and_reissue": "reissue_in_progress"}.get(
        c.decision or "", "concluded"
    )  # type: ignore[return-value]  # the three literal words


def _case_out(found: object, actions: list[str]) -> PostIssuanceCaseOut:
    from abacus.modules.assurance.post_issuance import Case

    c = cast(Case, found)
    ev = c.evaluation
    return PostIssuanceCaseOut(
        case_id=c.case_id,
        ref=c.ref,
        type=_TYPE_OUT[c.type],
        standard=cast(Literal["au_c_560", "au_c_585"] | None, c.standard),
        source_kind=cast(Source, c.source_kind),
        received_at=c.received_at,
        description=c.description,
        status=_status(c),
        comparison=[
            PostIssuanceComparisonLineOut(
                line_key=ln.line_key,
                label=ln.label,
                as_certified=ln.as_certified,
                as_corrected=ln.as_corrected,
                difference=ln.difference,
            )
            for ln in c.comparison
        ],
        evaluation=None
        if ev is None
        else PostIssuanceEvaluationOut(
            total_difference=ev.total_difference,
            clearly_trivial=ev.clearly_trivial,
            overall_materiality=ev.overall_materiality,
            share_pct=ev.share_pct,
            materiality_version_id=ev.materiality_version_id,
            below_clearly_trivial=ev.below_clearly_trivial,
        ),
        allowed_actions=actions,
        source_evidence_version_id=c.source_evidence_version_id,
        disclosure_affected=None if ev is None else ev.disclosure_affected,
        options=[cast(DecisionOption, o) for o in c.options],
        recommended_option=cast(DecisionOption | None, c.recommended),
        decision=cast(DecisionOption | None, c.decision),
        decided_by_user_id=c.decided_by,
        decided_at=c.decided_at,
    )


async def _actions(ctx: AuthContext, work_item_id: UUID) -> list[str]:
    from abacus.modules.engagements.api import get_ref, work_item_engagement
    from abacus.modules.identity.api import allowed_actions

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None or ctx.tenant.actor_kind != "human":
        return []
    ref = await get_ref(ctx, engagement_id)
    wanted = ("post_issuance.analyse", "post_issuance.decide", "post_issuance.reissue")
    return sorted(await allowed_actions(ctx, ref.resource(), wanted))


@post_issuance_router.get(
    _C, action="post_issuance.read", response_model=PostIssuanceCaseListOut, errors=(501,)
)
async def post_issuance_cases_route(work_item_id: UUID, ctx: Ctx) -> PostIssuanceCaseListOut:
    await _on(ctx)
    from abacus.modules.assurance import post_issuance as pi
    from abacus.modules.engagements.api import work_item_engagement

    found = await pi.cases(ctx, work_item_id)
    actions = await _actions(ctx, work_item_id)
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    locked = (
        None if engagement_id is None else await pi.archive_locked_at(ctx.tenant, engagement_id)
    )
    return PostIssuanceCaseListOut(
        items=[_case_out(c, actions) for c in found], archive_locked_at=locked
    )


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
    from abacus.modules.assurance import post_issuance as pi

    found = await pi.case(ctx, work_item_id, case_id)
    return _case_out(found, await _actions(ctx, work_item_id))


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
    """Only on an archived audit (409 `not_archived`); the locked documentation is never edited
    (AC-17)."""
    await _human(ctx, "post_issuance.create")
    from abacus.modules.assurance import post_issuance as pi

    found = await pi.open_case(
        ctx,
        work_item_id,
        type=cast(pi.CaseType, _TYPE_IN[body.type]),
        source_kind=body.source_kind,
        description=body.description,
        source_evidence_version_id=body.source_evidence_version_id,
    )
    return _case_out(found, await _actions(ctx, work_item_id))


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
    """409 `comparison_unavailable` (DV-9); the analysis ends with the not-decided sentence. The
    agent's analysis prompt lands with its capability task (ADR-079: after its eval suite,
    Q-05-T10): until then a compared case answers 501."""
    await _human(ctx, "post_issuance.analyse")
    from abacus.modules.assurance import post_issuance as pi

    await pi.require_comparison(ctx, work_item_id, case_id)
    raise NotImplementedYet


@post_issuance_router.post(
    f"{_C}/{{case_id}}/comparison",
    action="post_issuance.analyse",
    response_model=PostIssuanceCaseOut,
    errors=(409,),
)
async def post_issuance_comparison_route(
    work_item_id: UUID,
    case_id: UUID,
    body: PostIssuanceComparisonIn,
    ctx: Ctx,
    key: IdempotencyKey,
) -> PostIssuanceCaseOut:
    """AC-15: the code compares the corrected figures with A-05's certified lines and evaluates
    the difference against the materiality in force at release (409 `comparison_unavailable`
    when no line matches)."""
    await _human(ctx, "post_issuance.analyse")
    from abacus.modules.assurance import post_issuance as pi

    found = await pi.compare_case(
        ctx,
        work_item_id,
        case_id,
        body.corrected,
        disclosure_affected=body.disclosure_affected,
    )
    return _case_out(found, await _actions(ctx, work_item_id))


@post_issuance_router.post(
    f"{_C}/{{case_id}}/decision",
    action="post_issuance.decide",
    response_model=PostIssuanceCaseOut,
    errors=(409,),
)
async def post_issuance_decision_route(
    work_item_id: UUID,
    case_id: UUID,
    body: PostIssuanceDecisionIn,
    ctx: Ctx,
    key: IdempotencyKey,
) -> PostIssuanceCaseOut:
    """The engagement partner, fresh MFA, among the code's options, with a rationale (DEC-5724)."""
    await _human(ctx, "post_issuance.decide")
    from abacus.modules.assurance import post_issuance as pi

    found = await pi.record_case_decision(
        ctx, work_item_id, case_id, decision=body.decision, rationale=body.rationale
    )
    return _case_out(found, await _actions(ctx, work_item_id))


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
