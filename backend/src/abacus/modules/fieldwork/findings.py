"""Findings and the summary of uncorrected misstatements (SPEC-043; TASK-107).

A team member raises a finding, on a fieldwork row or by hand; a senior, manager or partner
records a misstatement on it (the newest counts; earlier ones stay, ADR-004). Code totals the
uncorrected misstatements above clearly trivial, by kind, against performance and overall
materiality (ADR-050): people judge what it means.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.models import Finding, Misstatement
from abacus.modules.fieldwork.repository import (
    findings_of,
    get_finding,
    get_item,
    get_procedure,
    insert_finding,
    insert_misstatement,
    newest_materiality,
    newest_misstatements,
)
from abacus.modules.identity.api import AuthContext, authorise, engagement_team

KINDS: Final = ("factual", "judgmental", "projected")


class FindingInvalid(DomainInvalid):
    code = "finding_invalid"


@dataclass(frozen=True)
class MisstatementView:
    kind: str
    amount: Decimal
    account_code: str | None
    corrected: bool
    recorded_by_name: str
    recorded_at: datetime


@dataclass(frozen=True)
class FindingView:
    id: UUID
    title: str
    description: str | None
    procedure_id: UUID | None
    item_id: UUID | None
    raised_by_name: str
    raised_at: datetime
    misstatement: MisstatementView | None


@dataclass(frozen=True)
class KindTotal:
    kind: str
    count: int
    total: Decimal


@dataclass(frozen=True)
class Summary:
    materiality_set: bool
    overall: Decimal | None
    performance: Decimal | None
    trivial: Decimal | None
    by_kind: list[KindTotal]
    total: Decimal
    position: str  # below_performance | at_or_above_performance | at_or_above_overall | unknown


def summarise(
    misstatements: Sequence[Misstatement],
    overall: Decimal | None,
    performance: Decimal | None,
    trivial: Decimal | None,
) -> tuple[list[KindTotal], Decimal, str]:
    """AC-3, by code (ADR-050): uncorrected misstatements above clearly trivial (by absolute
    amount), totalled by kind; the grand total's absolute value against materiality."""
    floor = trivial if trivial is not None else Decimal(0)
    kept = [m for m in misstatements if not m.corrected and abs(m.amount) > floor]
    by_kind = [
        KindTotal(
            kind,
            sum(1 for m in kept if m.kind == kind),
            sum((m.amount for m in kept if m.kind == kind), Decimal(0)),
        )
        for kind in KINDS
    ]
    total = sum((k.total for k in by_kind), Decimal(0))
    if overall is None or performance is None:
        return by_kind, total, "unknown"
    size = abs(total)
    position = (
        "at_or_above_overall"
        if size >= overall
        else "at_or_above_performance"
        if size >= performance
        else "below_performance"
    )
    return by_kind, total, position


async def raise_finding(
    ctx: AuthContext,
    engagement_id: UUID,
    title: str,
    description: str | None,
    procedure_id: UUID | None,
    item_id: UUID | None,
) -> UUID:
    """AC-1."""
    title = title.strip()
    text = (description or "").strip() or None
    if not 1 <= len(title) <= 200 or (text is not None and len(text) > 2000):
        raise FindingInvalid("title")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "finding.raise", ref.resource())
        if procedure_id is not None:
            procedure = await get_procedure(tx.session, procedure_id)
            if procedure is None or procedure.engagement_id != engagement_id:
                raise NotFound("procedure")
        if item_id is not None and (
            procedure_id is None or await get_item(tx.session, item_id) is None
        ):
            raise NotFound("selected_item")
        finding_id = await insert_finding(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            procedure_id=procedure_id,
            selected_item_id=item_id,
            title=title,
            description=text,
            raised_by=ctx.user_id,
        )
        tx.record("finding.raised", target=Target("finding", finding_id))
    return finding_id


async def record_misstatement(
    ctx: AuthContext,
    engagement_id: UUID,
    finding_id: UUID,
    kind: str,
    amount: Decimal,
    account_code: str | None,
    corrected: bool,
) -> None:
    """AC-2."""
    if kind not in KINDS or amount == 0:
        raise FindingInvalid("misstatement")
    code = (account_code or "").strip()[:64] or None
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "misstatement.set", ref.resource())
        finding = await get_finding(tx.session, finding_id)
        if finding is None or finding.engagement_id != engagement_id:
            raise NotFound("finding")
        await insert_misstatement(
            tx.session,
            tenant_id=ctx.tenant_id,
            finding_id=finding_id,
            kind=kind,
            amount=amount,
            account_code=code,
            corrected=corrected,
            recorded_by=ctx.user_id,
        )
        tx.record(
            "misstatement.recorded",
            target=Target("finding", finding_id),
            after=Ref(kind=KINDS.index(kind), corrected=int(corrected)),
        )


async def _read(
    ctx: AuthContext, engagement_id: UUID
) -> tuple[Sequence[Finding], dict[UUID, Misstatement]]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await findings_of(session, ctx, engagement_id)
        newest = await newest_misstatements(session, [f.id for f in found])
    return found, newest


async def findings_for(ctx: AuthContext, engagement_id: UUID) -> list[FindingView]:
    """AC-5: the register, oldest first."""
    found, newest = await _read(ctx, engagement_id)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    views: list[FindingView] = []
    for f in found:
        m = newest.get(f.id)
        views.append(
            FindingView(
                f.id,
                f.title,
                f.description,
                f.procedure_id,
                f.selected_item_id,
                names.get(f.raised_by, ""),
                f.created_at,
                MisstatementView(
                    m.kind,
                    m.amount,
                    m.account_code,
                    m.corrected,
                    names.get(m.recorded_by, ""),
                    m.created_at,
                )
                if m is not None
                else None,
            )
        )
    return views


async def summary_for(ctx: AuthContext, engagement_id: UUID) -> Summary:
    """AC-3."""
    _found, newest = await _read(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        materiality = await newest_materiality(session, engagement_id)
    overall = materiality.overall if materiality else None
    performance = materiality.performance if materiality else None
    trivial = materiality.trivial if materiality else None
    by_kind, total, position = summarise(list(newest.values()), overall, performance, trivial)
    return Summary(
        materiality is not None, overall, performance, trivial, by_kind, total, position
    )
