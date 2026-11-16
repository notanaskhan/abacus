"""The fieldwork-testing contract stub, workpapers half (A-08-T05; SPEC-657 F1, F2; DEC-5032).
Contract: `docs/contracts/fieldwork-testing.md`; screen AUD-12 (all variants).

Runs, L1 adoption, exceptions, control deviations and the deterministic export on A-05's shared
attribute grid (`GET /v1/tests/{test_id}` and the human marks stay A-05's). One action each:
client 404; the flag `audits.fieldwork_testing`; then 501 until A-08-T14 / T24. The record's
service resolves its work item and authorises there (A-08-T14).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDITS_FIELDWORK_TESTING
from abacus.kernel.classification import classified
from abacus.kernel.clock import now
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]


class TestRunOut(BaseModel):
    """A `fieldwork_attribute` run started by a person; attributed '<person> via Agent'."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    items: Annotated[int, Field(ge=0), classified("internal")]
    initiator_name: Annotated[str, classified("confidential")]


class AdoptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seen_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class AdoptOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sign_off_id: Annotated[UUID, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    adopted_at: Annotated[datetime, classified("internal")]


class ExceptionPrefillOut(BaseModel):
    """SHL-15's prefill; a person submits it through `assurance.api.record_finding`."""

    model_config = ConfigDict(frozen=True)

    test_id: Annotated[UUID, classified("internal")]
    item_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, Field(max_length=300), classified("confidential")]
    amount: Annotated[Decimal | None, classified("confidential")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class DeviationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_position: Annotated[int, Field(ge=1), classified("internal")]
    attribute_key: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    description: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    citation_ids: Annotated[list[UUID], Field(min_length=1), classified("internal")]


class DeviationLogOut(BaseModel):
    """'0 deviations · upper deviation limit 8.8% < tolerable 10%' (code's UDL, A-03)."""

    model_config = ConfigDict(frozen=True)

    deviations: Annotated[int, Field(ge=0), classified("internal")]
    sample_size: Annotated[int, Field(ge=1), classified("internal")]
    upper_deviation_limit: Annotated[Decimal, classified("internal")]
    tolerable_rate: Annotated[Decimal, classified("internal")]
    comparison: Annotated[Literal["below", "above"], classified("internal")]


router = AbacusRouter(prefix="/v1", tags=["fieldwork-testing"])
_T = "/tests/{test_id}"


async def _gate(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("test")
    if not await flag_enabled(ctx.tenant, AUDITS_FIELDWORK_TESTING):
        raise NotFound(AUDITS_FIELDWORK_TESTING.name)


@router.post(
    f"{_T}/runs", action="test.run", response_model=TestRunOut, status_code=202, errors=(409, 501)
)
async def start_run(test_id: UUID, ctx: Ctx, _key: IdempotencyKey) -> TestRunOut:
    """Begin… / Re-run (behind `audits.fieldwork_agents`; DF-04 on a closed data boundary)."""
    await _gate(ctx)
    raise NotImplementedYet("A-08-T24")


@router.post(f"{_T}/adopt", action="test.adopt", response_model=AdoptOut, errors=(409, 501))
async def fieldwork_test_adopt(
    test_id: UUID, body: AdoptIn, ctx: Ctx, _key: IdempotencyKey
) -> AdoptOut:
    """L1 through `review.api.record_sign_off` with the version's content hash."""
    await _gate(ctx)
    from abacus.modules.workpapers import fieldwork_tests as ft

    signed, content_hash = await ft.adopt(ctx, test_id, body.seen_hash)
    return AdoptOut(
        sign_off_id=signed, content_hash=content_hash, adopted_at=await now(ctx.tenant)
    )


@router.post(
    f"{_T}/items/{{item_id}}/exception",
    action="finding.create",
    response_model=ExceptionPrefillOut,
    errors=(501,),
)
async def fieldwork_test_exception_prefill(
    test_id: UUID, item_id: UUID, ctx: Ctx
) -> ExceptionPrefillOut:
    await _gate(ctx)
    from abacus.modules.workpapers import fieldwork_tests as ft

    found = await ft.exception_prefill(ctx, test_id, item_id)
    return ExceptionPrefillOut(
        test_id=test_id,
        item_id=item_id,
        title=found.title[:300],
        amount=None,
        citation_ids=list(found.citation_ids),
    )


@router.post(
    f"{_T}/deviations",
    action="test.mark",
    response_model=DeviationLogOut,
    status_code=201,
    errors=(409, 501),
)
async def log_deviation(
    test_id: UUID, body: DeviationIn, ctx: Ctx, _key: IdempotencyKey
) -> DeviationLogOut:
    """Insert-only; the UDL recomputes in code (0 of 25 ⇒ 8.8%; 2 of 25 ⇒ 19.9%)."""
    await _gate(ctx)
    from abacus.modules.workpapers import fieldwork_tests as ft

    log = await ft.log_at_position(
        ctx, test_id, body.item_position, body.attribute_key, body.description
    )
    tolerable = await ft.tolerable_rate(ctx, test_id)
    udl = log.udl_pct / 100  # the engine answers a percent; the contract a fraction
    return DeviationLogOut(
        deviations=log.deviations,
        sample_size=max(log.tested, 1),
        upper_deviation_limit=udl,
        tolerable_rate=tolerable if tolerable is not None else Decimal("0"),
        comparison="below" if tolerable is not None and udl < tolerable else "above",
    )


@router.get(f"{_T}/export.xlsx", action="test.export", response_model=bytes, errors=(501,))
async def export_test(test_id: UUID, ctx: Ctx) -> Response:
    """'JE Testing.xlsx': byte-identical per version, accounts masked to the last four."""
    await _gate(ctx)
    from abacus.modules.workpapers import fieldwork_tests as ft

    return Response(
        content=await ft.export_xlsx(ctx, test_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
