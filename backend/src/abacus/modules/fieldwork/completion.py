"""Completion: deficiency severity, proposed adjusting entries and the representation list
(SPEC-301; TASK-302).

A senior, manager or partner proposes a finding's severity; only the engagement partner concludes
it, with a rationale; a manager or the partner records when it was communicated. The team
proposes entries (AJE-n, RJE-n) whose debits equal their credits, checked by code (ADR-050); a
manager or the partner approves them and records the client's answer: accepted, or declined and
passed. The representation list holds specific representations; code lists what still lacks one.
The firm never posts an entry, and the agent does nothing here (ADR-005).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.models import (
    Adjustment,
    AdjustmentEvent,
    AdjustmentLine,
    FindingCommunication,
    FindingSeverity,
    Representation,
    RepresentationRemoval,
)
from abacus.modules.fieldwork.repository import (
    adjustment_events_of,
    adjustment_lines_of,
    adjustments_of,
    communications_of,
    findings_of,
    get_adjustment,
    get_finding,
    insert_row,
    next_adjustment_number,
    representations_of,
    severities_of,
)
from abacus.modules.identity.api import AuthContext, authorise, engagement_team

SEVERITIES: Final = ("deficiency", "significant_deficiency", "material_weakness")
KINDS: Final = ("aje", "rje")
MAX_LINES: Final = 50


class CompletionInvalid(DomainInvalid):
    code = "completion_invalid"


class NotConcluded(DomainConflict):
    """A deficiency is communicated only once the partner has concluded its severity."""

    code = "not_concluded"


class AdjustmentState(DomainConflict):
    """Approve once; record the client's answer once, after approval."""

    code = "adjustment_state"


def _text(value: str | None, limit: int, *, required: bool = False) -> str | None:
    text = (value or "").strip() or None
    if (required and text is None) or (text is not None and len(text) > limit):
        raise CompletionInvalid("text")
    return text


# --- Deficiency severity ------------------------------------------------------------------------


@dataclass(frozen=True)
class Deficiency:
    status: str  # proposed | concluded | communicated
    proposed: str | None
    proposed_by_name: str | None
    concluded: str | None
    concluded_by_name: str | None
    concluded_at: datetime | None
    conclusion_rationale: str | None
    communicated_on: date | None
    communicated_to: str | None


def deficiency_of(
    severities: Sequence[FindingSeverity],
    communications: Sequence[FindingCommunication],
    names: dict[UUID, str],
) -> Deficiency | None:
    """One finding's severity records (newest first) folded into its state, by code."""
    proposed = next((s for s in severities if s.stage == "proposed"), None)
    concluded = next((s for s in severities if s.stage == "concluded"), None)
    if proposed is None and concluded is None:
        return None
    told = next(
        (c for c in communications if concluded and c.created_at >= concluded.created_at), None
    )
    status = "communicated" if told else "concluded" if concluded else "proposed"
    return Deficiency(
        status,
        proposed.severity if proposed else None,
        names.get(proposed.set_by, "") if proposed else None,
        concluded.severity if concluded else None,
        names.get(concluded.set_by, "") if concluded else None,
        concluded.created_at if concluded else None,
        concluded.rationale if concluded else None,
        told.communicated_on if told else None,
        told.recipients if told else None,
    )


async def deficiencies_for(
    ctx: AuthContext, finding_ids: Sequence[UUID], names: dict[UUID, str]
) -> dict[UUID, Deficiency]:
    async with tenant_session(ctx.tenant) as session:
        severities = await severities_of(session, finding_ids)
        communications = await communications_of(session, finding_ids)
    out: dict[UUID, Deficiency] = {}
    for fid in finding_ids:
        found = deficiency_of(
            [s for s in severities if s.finding_id == fid],
            [c for c in communications if c.finding_id == fid],
            names,
        )
        if found is not None:
            out[fid] = found
    return out


async def set_severity(
    ctx: AuthContext,
    engagement_id: UUID,
    finding_id: UUID,
    stage: str,
    severity: str,
    rationale: str | None,
) -> None:
    """AC-1 (propose) and AC-2 (the partner concludes, with a rationale)."""
    if stage not in ("proposed", "concluded") or severity not in SEVERITIES:
        raise CompletionInvalid("severity")
    text = _text(rationale, 2000, required=stage == "concluded")
    action = "finding.conclude_severity" if stage == "concluded" else "finding.propose_severity"
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, action, ref.resource())
        finding = await get_finding(tx.session, finding_id)
        if finding is None or finding.engagement_id != engagement_id:
            raise NotFound("finding")
        await insert_row(
            tx.session,
            FindingSeverity,
            tenant_id=ctx.tenant_id,
            finding_id=finding_id,
            stage=stage,
            severity=severity,
            rationale=text,
            set_by=ctx.user_id,
        )
        tx.record(
            f"finding.severity_{stage}",
            target=Target("finding", finding_id),
            after=Ref(severity=SEVERITIES.index(severity)),
        )


async def record_communication(
    ctx: AuthContext, engagement_id: UUID, finding_id: UUID, on: date, recipients: str
) -> None:
    """AC-3: when and to whom a concluded deficiency was communicated."""
    to = _text(recipients, 300, required=True)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "finding.communicate", ref.resource())
        finding = await get_finding(tx.session, finding_id)
        if finding is None or finding.engagement_id != engagement_id:
            raise NotFound("finding")
        if not any(s.stage == "concluded" for s in await severities_of(tx.session, [finding_id])):
            raise NotConcluded(str(finding_id))
        await insert_row(
            tx.session,
            FindingCommunication,
            tenant_id=ctx.tenant_id,
            finding_id=finding_id,
            communicated_on=on,
            recipients=to,
            recorded_by=ctx.user_id,
        )
        tx.record("finding.communicated", target=Target("finding", finding_id))


# --- Proposed entries ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineIn:
    account_code: str
    debit: Decimal
    credit: Decimal


def check_lines(lines: Sequence[LineIn]) -> Decimal:
    """AC-4, by code: two or more one-sided lines whose debits equal their credits; the total."""
    if not 2 <= len(lines) <= MAX_LINES:
        raise CompletionInvalid("lines")
    for line in lines:
        code = line.account_code.strip()
        if not 1 <= len(code) <= 64 or line.debit < 0 or line.credit < 0:
            raise CompletionInvalid("line")
        if (line.debit == 0) == (line.credit == 0):
            raise CompletionInvalid("line_side")
    debits = sum((line.debit for line in lines), Decimal(0))
    if debits != sum((line.credit for line in lines), Decimal(0)):
        raise CompletionInvalid("unbalanced")
    return debits


@dataclass(frozen=True)
class LineView:
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class AdjustmentView:
    id: UUID
    ref: str
    kind: str
    description: str
    finding_id: UUID | None
    lines: list[LineView]
    total: Decimal
    status: str  # proposed | approved | client_accepted | client_declined
    raised_by_name: str
    raised_at: datetime
    approved_by_name: str | None
    response_note: str | None


def status_of(events: Sequence[AdjustmentEvent]) -> str:
    kinds = {e.kind for e in events}
    for kind in ("client_accepted", "client_declined", "approved"):
        if kind in kinds:
            return kind
    return "proposed"


async def propose_adjustment(
    ctx: AuthContext,
    engagement_id: UUID,
    kind: str,
    description: str,
    finding_id: UUID | None,
    lines: Sequence[LineIn],
) -> UUID:
    """AC-4."""
    if kind not in KINDS:
        raise CompletionInvalid("kind")
    text = _text(description, 500, required=True)
    check_lines(lines)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "adjustment.propose", ref.resource())
        if finding_id is not None:
            finding = await get_finding(tx.session, finding_id)
            if finding is None or finding.engagement_id != engagement_id:
                raise NotFound("finding")
        adjustment_id = await insert_row(
            tx.session,
            Adjustment,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            kind=kind,
            number=await next_adjustment_number(tx.session, engagement_id, kind),
            finding_id=finding_id,
            description=text,
            raised_by=ctx.user_id,
        )
        for position, line in enumerate(lines):
            await insert_row(
                tx.session,
                AdjustmentLine,
                tenant_id=ctx.tenant_id,
                adjustment_id=adjustment_id,
                position=position,
                account_code=line.account_code.strip(),
                debit=line.debit,
                credit=line.credit,
            )
        tx.record(
            "adjustment.proposed",
            target=Target("adjustment", adjustment_id),
            after=Ref(lines=len(lines)),
        )
    return adjustment_id


async def record_adjustment_event(
    ctx: AuthContext, engagement_id: UUID, adjustment_id: UUID, kind: str, note: str | None
) -> None:
    """AC-5: approve once; then the client's answer once (accepted, or declined and passed)."""
    if kind not in ("approved", "client_accepted", "client_declined"):
        raise CompletionInvalid("event")
    text = _text(note, 1000)
    action = "adjustment.approve" if kind == "approved" else "adjustment.record_response"
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, action, ref.resource())
        adjustment = await get_adjustment(tx.session, adjustment_id)
        if adjustment is None or adjustment.engagement_id != engagement_id:
            raise NotFound("adjustment")
        status = status_of(await adjustment_events_of(tx.session, [adjustment_id]))
        if (kind == "approved") != (status == "proposed") or (
            kind != "approved" and status != "approved"
        ):
            raise AdjustmentState(status)
        await insert_row(
            tx.session,
            AdjustmentEvent,
            tenant_id=ctx.tenant_id,
            adjustment_id=adjustment_id,
            kind=kind,
            note=text,
            by_user=ctx.user_id,
        )
        tx.record(f"adjustment.{kind}", target=Target("adjustment", adjustment_id))


async def adjustments_for(ctx: AuthContext, engagement_id: UUID) -> list[AdjustmentView]:
    """AC-6: the proposed entries, oldest first."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await adjustments_of(session, ctx, engagement_id)
        ids = [a.id for a in found]
        lines = await adjustment_lines_of(session, ids)
        events = await adjustment_events_of(session, ids)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    views: list[AdjustmentView] = []
    for a in found:
        mine = [
            LineView(x.account_code, x.debit, x.credit) for x in lines if x.adjustment_id == a.id
        ]
        evs = [e for e in events if e.adjustment_id == a.id]
        approved = next((e for e in evs if e.kind == "approved"), None)
        answer = next((e for e in evs if e.kind.startswith("client_")), None)
        views.append(
            AdjustmentView(
                a.id,
                f"{a.kind.upper()}-{a.number}",
                a.kind,
                a.description,
                a.finding_id,
                mine,
                sum((x.debit for x in mine), Decimal(0)),
                status_of(evs),
                names.get(a.raised_by, ""),
                a.created_at,
                names.get(approved.by_user, "") if approved else None,
                answer.note if answer else None,
            )
        )
    return views


# --- Representations ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RepresentationView:
    id: UUID
    body: str
    finding_id: UUID | None
    adjustment_id: UUID | None
    raised_by_name: str
    raised_at: datetime


@dataclass(frozen=True)
class Gap:
    kind: str  # finding | adjustment
    id: UUID
    label: str


@dataclass(frozen=True)
class RepresentationList:
    items: list[RepresentationView]
    passed: list[str]  # refs of entries the client declined: the attached summary lists them
    gaps: list[Gap]


def gaps_of(
    reps: Sequence[Representation],
    concluded: dict[UUID, str],
    passed: dict[UUID, str],
) -> list[Gap]:
    """AC-8, by code: concluded deficiencies and passed entries no representation covers."""
    covered_findings = {r.finding_id for r in reps if r.finding_id is not None}
    covered_entries = {r.adjustment_id for r in reps if r.adjustment_id is not None}
    return [
        *(Gap("finding", fid, t) for fid, t in concluded.items() if fid not in covered_findings),
        *(Gap("adjustment", aid, r) for aid, r in passed.items() if aid not in covered_entries),
    ]


async def representations_for(ctx: AuthContext, engagement_id: UUID) -> RepresentationList:
    """AC-7, AC-8."""
    entries = await adjustments_for(ctx, engagement_id)  # authorises procedure.read
    async with tenant_session(ctx.tenant) as session:
        reps = await representations_of(session, ctx, engagement_id)
        findings = await findings_of(session, ctx, engagement_id)
        severities = await severities_of(session, [f.id for f in findings])
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    concluded_ids = {s.finding_id for s in severities if s.stage == "concluded"}
    concluded = {f.id: f.title for f in findings if f.id in concluded_ids}
    passed = {a.id: a.ref for a in entries if a.status == "client_declined"}
    return RepresentationList(
        [
            RepresentationView(
                r.id,
                r.body,
                r.finding_id,
                r.adjustment_id,
                names.get(r.raised_by, ""),
                r.created_at,
            )
            for r in reps
        ],
        list(passed.values()),
        gaps_of(reps, concluded, passed),
    )


async def add_representation(
    ctx: AuthContext,
    engagement_id: UUID,
    body: str,
    finding_id: UUID | None,
    adjustment_id: UUID | None,
) -> None:
    """AC-7."""
    text = _text(body, 2000, required=True)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "representation.edit", ref.resource())
        if finding_id is not None:
            finding = await get_finding(tx.session, finding_id)
            if finding is None or finding.engagement_id != engagement_id:
                raise NotFound("finding")
        if adjustment_id is not None:
            entry = await get_adjustment(tx.session, adjustment_id)
            if entry is None or entry.engagement_id != engagement_id:
                raise NotFound("adjustment")
        rep_id = await insert_row(
            tx.session,
            Representation,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            body=text,
            finding_id=finding_id,
            adjustment_id=adjustment_id,
            raised_by=ctx.user_id,
        )
        tx.record("representation.added", target=Target("representation", rep_id))


async def remove_representation(ctx: AuthContext, engagement_id: UUID, rep_id: UUID) -> None:
    """AC-7: off the list; the record stays (ADR-004)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "representation.edit", ref.resource())
        listed = await representations_of(tx.session, ctx, engagement_id)
        if rep_id not in {r.id for r in listed}:
            raise NotFound("representation")
        await insert_row(
            tx.session,
            RepresentationRemoval,
            tenant_id=ctx.tenant_id,
            representation_id=rep_id,
            removed_by=ctx.user_id,
        )
        tx.record("representation.removed", target=Target("representation", rep_id))
