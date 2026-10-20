"""Planning: materiality as the engagement partner's decision, and the risk register (SPEC-300;
TASK-301).

A manager or the partner proposes materiality; code computes the amounts from the basis
(ADR-050). Only the engagement partner decides it, with a rationale, and selection waits for the
decision. The team records risks (R1, R2…, insert-only versions); code combines inherent and
control risk into the risk of material misstatement. The partner approves a significant risk or a
rebuttal of a presumed fraud risk. People decide; the agent does nothing here (ADR-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.repository import (
    get_risk,
    insert_materiality_decision,
    insert_risk,
    insert_risk_approval,
    insert_risk_version,
    materiality_decisions,
    materiality_versions,
    newest_risk_versions,
    next_risk_number,
    risk_approvals,
    risks_of,
)
from abacus.modules.identity.api import AuthContext, authorise, engagement_team

LEVELS: Final = ("financial_statement", "assertion")
INHERENT: Final = ("low", "moderate", "high")
CONTROL: Final = ("low", "moderate", "high", "maximum")
FRAUD: Final = ("none", "presumed", "rebuttal")
ASSERTIONS: Final = (
    "existence",
    "completeness",
    "accuracy",
    "valuation",
    "cut_off",
    "rights_obligations",
    "presentation",
)
_SCORE: Final = {"low": 1, "moderate": 2, "high": 3, "maximum": 3}
_HUNDRED: Final = Decimal(100)


class PlanningInvalid(DomainInvalid):
    code = "planning_invalid"


class AlreadyDecided(DomainConflict):
    code = "already_decided"


class NothingToApprove(DomainConflict):
    """The risk's current version has no significant risk or rebuttal, or it's approved."""

    code = "nothing_to_approve"


# --- Materiality --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Amounts:
    overall: Decimal
    performance: Decimal
    trivial: Decimal


def _round(value: Decimal) -> Decimal:
    """To the nearest hundred from 1,000 up, else the nearest dollar (never below one)."""
    step = _HUNDRED if value >= 1000 else Decimal(1)
    return max((value / step).quantize(Decimal(1), ROUND_HALF_UP) * step, Decimal(1))


def compute(
    basis_amount: Decimal, rate_pct: Decimal, performance_pct: Decimal, trivial_pct: Decimal
) -> Amounts:
    """AC-1, by code (ADR-050): overall is the rate of the basis; performance and clearly
    trivial are percentages of overall."""
    for pct in (rate_pct, performance_pct, trivial_pct):
        if not Decimal(0) < pct <= _HUNDRED:
            raise PlanningInvalid("percentage")
    if basis_amount <= 0 or trivial_pct > performance_pct:
        raise PlanningInvalid("basis")
    overall = _round(basis_amount * rate_pct / _HUNDRED)
    performance = min(_round(overall * performance_pct / _HUNDRED), overall)
    return Amounts(
        overall, performance, min(_round(overall * trivial_pct / _HUNDRED), performance)
    )


@dataclass(frozen=True)
class MaterialityVersionView:
    id: UUID
    version: int
    status: str  # proposed | decided | superseded
    overall: Decimal
    performance: Decimal
    trivial: Decimal
    benchmark: str
    basis_amount: Decimal | None
    rate_pct: Decimal | None
    performance_pct: Decimal | None
    trivial_pct: Decimal | None
    rationale: str | None
    set_by_name: str
    set_at: datetime
    decided_by_name: str | None
    decided_at: datetime | None
    decision_rationale: str | None


async def materiality_history(
    ctx: AuthContext, engagement_id: UUID
) -> list[MaterialityVersionView]:
    """AC-3: every version, newest first; only the newest can be proposed or decided."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        versions = await materiality_versions(session, engagement_id)
        decisions = await materiality_decisions(session, [v.id for v in versions])
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    views: list[MaterialityVersionView] = []
    for i, v in enumerate(versions):
        d = decisions.get(v.id)
        status = "superseded" if i > 0 else "decided" if d is not None else "proposed"
        views.append(
            MaterialityVersionView(
                v.id,
                len(versions) - i,
                status,
                v.overall,
                v.performance,
                v.trivial,
                v.benchmark,
                v.basis_amount,
                v.rate_pct,
                v.performance_pct,
                v.trivial_pct,
                v.rationale,
                names.get(v.set_by, ""),
                v.created_at,
                names.get(d.decided_by, "") if d else None,
                d.created_at if d else None,
                d.rationale if d else None,
            )
        )
    return views


async def decide_materiality(ctx: AuthContext, engagement_id: UUID, rationale: str) -> None:
    """AC-2: the engagement partner decides the newest version, with a rationale."""
    text = rationale.strip()
    if not 1 <= len(text) <= 2000:
        raise PlanningInvalid("rationale")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "materiality.decide", ref.resource())
        versions = await materiality_versions(tx.session, engagement_id)
        if not versions:
            raise NotFound("materiality")
        newest = versions[0]
        if await materiality_decisions(tx.session, [newest.id]):
            raise AlreadyDecided(str(newest.id))
        await insert_materiality_decision(
            tx.session,
            tenant_id=ctx.tenant_id,
            materiality_id=newest.id,
            rationale=text,
            decided_by=ctx.user_id,
        )
        tx.record("materiality.decided", target=Target("engagement", engagement_id))


# --- Risks --------------------------------------------------------------------------------------


def rmm(inherent: str, control: str) -> str:
    """AC-4, by code: the risk of material misstatement from inherent and control risk."""
    total = _SCORE[inherent] + _SCORE[control]
    return "high" if total >= 5 else "moderate" if total == 4 else "low"


@dataclass(frozen=True)
class RiskIn:
    title: str
    area: str
    level: str
    assertions: list[str]
    inherent: str
    control: str
    significant: bool
    fraud: str
    rationale: str | None


@dataclass(frozen=True)
class RiskView:
    id: UUID
    code: str
    title: str
    area: str
    level: str
    assertions: list[str]
    inherent: str
    control: str
    rmm: str
    significant: bool
    fraud: str
    rationale: str | None
    needs_approval: bool
    approved_by_name: str | None
    approved_at: datetime | None
    recorded_by_name: str
    recorded_at: datetime


def clean_risk(body: RiskIn) -> RiskIn:
    title, area = body.title.strip(), body.area.strip()
    text = (body.rationale or "").strip() or None
    if (
        not 1 <= len(title) <= 200
        or not 1 <= len(area) <= 120
        or body.level not in LEVELS
        or body.inherent not in INHERENT
        or body.control not in CONTROL
        or body.fraud not in FRAUD
        or any(a not in ASSERTIONS for a in body.assertions)
        or (text is not None and len(text) > 2000)
    ):
        raise PlanningInvalid("risk")
    if (body.significant or body.fraud == "rebuttal") and text is None:
        raise PlanningInvalid("rationale")  # AC-5: the partner reads why
    kept = [a for a in ASSERTIONS if a in body.assertions]
    return RiskIn(
        title,
        area,
        body.level,
        kept,
        body.inherent,
        body.control,
        body.significant,
        body.fraud,
        text,
    )


async def record_risk(
    ctx: AuthContext, engagement_id: UUID, risk_id: UUID | None, body: RiskIn
) -> UUID:
    """AC-4: a new risk, or a new version of one; insert-only."""
    clean = clean_risk(body)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "risk.assess", ref.resource())
        if risk_id is None:
            risk_id = await insert_risk(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                number=await next_risk_number(tx.session, engagement_id),
                raised_by=ctx.user_id,
            )
        else:
            risk = await get_risk(tx.session, risk_id)
            if risk is None or risk.engagement_id != engagement_id:
                raise NotFound("risk")
        await insert_risk_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            risk_id=risk_id,
            title=clean.title,
            area=clean.area,
            level=clean.level,
            assertions=clean.assertions,
            inherent=clean.inherent,
            control=clean.control,
            significant=clean.significant,
            fraud=clean.fraud,
            rationale=clean.rationale,
            recorded_by=ctx.user_id,
        )
        tx.record(
            "risk.recorded",
            target=Target("risk", risk_id),
            after=Ref(significant=int(clean.significant), fraud=FRAUD.index(clean.fraud)),
        )
    return risk_id


async def approve_risk(
    ctx: AuthContext, engagement_id: UUID, risk_id: UUID, rationale: str | None
) -> None:
    """AC-5: the partner approves the current version's significant risk or rebuttal."""
    text = (rationale or "").strip() or None
    if text is not None and len(text) > 2000:
        raise PlanningInvalid("rationale")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "risk.approve", ref.resource())
        risk = await get_risk(tx.session, risk_id)
        if risk is None or risk.engagement_id != engagement_id:
            raise NotFound("risk")
        version = (await newest_risk_versions(tx.session, [risk_id]))[risk_id]
        if not (version.significant or version.fraud == "rebuttal") or await risk_approvals(
            tx.session, [version.id]
        ):
            raise NothingToApprove(str(risk_id))
        await insert_risk_approval(
            tx.session,
            tenant_id=ctx.tenant_id,
            risk_version_id=version.id,
            rationale=text,
            approved_by=ctx.user_id,
        )
        tx.record("risk.approved", target=Target("risk", risk_id))


async def risks_for(ctx: AuthContext, engagement_id: UUID) -> list[RiskView]:
    """AC-6: the register, R1 first."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        risks = await risks_of(session, ctx, engagement_id)
        versions = await newest_risk_versions(session, [r.id for r in risks])
        approvals = await risk_approvals(session, [v.id for v in versions.values()])
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    views: list[RiskView] = []
    for r in risks:
        v = versions.get(r.id)
        if v is None:
            continue
        a = approvals.get(v.id)
        asks = v.significant or v.fraud == "rebuttal"
        views.append(
            RiskView(
                r.id,
                f"R{r.number}",
                v.title,
                v.area,
                v.level,
                list(v.assertions),
                v.inherent,
                v.control,
                rmm(v.inherent, v.control),
                v.significant,
                v.fraud,
                v.rationale,
                asks and a is None,
                names.get(a.approved_by, "") if a else None,
                a.created_at if a else None,
                names.get(v.recorded_by, ""),
                v.created_at,
            )
        )
    return views
