"""A-06-T11: the findings service (AUD-15; A-06 §4.3; SPEC-642; DEC-2063).

A finding is rooted on a P-04 issue (DEC-83: the issue holds lifecycle, assignee and events) and
carries the audit's facts in 0644's `audit_findings`:

- **Record** (`record_finding`): the issue on the workpaper it came from, then the finding with its
  next `F-nn`. A finding the agent raises lands under evaluation with its `why_surfaced` sealed as
  the agent's suggestion and must carry verified citations (422 `uncited_finding` otherwise,
  INV-2); a person's finding needs none.
- **List** (`findings_of`): rows with the severity bands' counts (material weakness, significant
  deficiency, deficiency, not a deficiency) and the badge of findings awaiting the partner.
- **Detail** with the code-computed evaluation (the row's `evaluation`, written by code only).
- **Resolve / not applicable**: through the issue (`review.api.move_issue`); the matrix denies the
  agent both (`finding.resolve`, `finding.mark_not_applicable`).
- **Convert** to a deficiency (Proposed, severity for the partner's card) or a misstatement
  (factual or judgmental with its amount; a projected one takes its figure from sampling, which
  answers 422 `projection_unavailable` until A-03's projection facts are exposed).

Severity and the SUM conclusion stay the engagement partner's C3 cards (INV-1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref, work_item_engagement
from abacus.modules.evidence.api import verified_citation_ids
from abacus.modules.identity.api import AuthContext, allowed_actions
from abacus.modules.review.api import create_issue, issue_row, move_issue

TARGET: Final = "audit_finding"
_FINGERPRINT: Final = "assurance.why_surfaced"
BANDS: Final = ("material_weakness", "significant_deficiency", "deficiency", "not_a_deficiency")
_ACTIONS: Final = (
    "finding.update",
    "finding.convert",
    "finding.resolve",
    "finding.mark_not_applicable",
    "finding.request_decision",
)


class UncitedFinding(DomainInvalid):
    """An agent's finding without a verified citation is never recorded (INV-2)."""

    code = "uncited_finding"


class FindingMoved(DomainConflict):
    code = "version_conflict"


class ProjectionUnavailable(DomainInvalid):
    code = "projection_unavailable"


@dataclass(frozen=True)
class NewFinding:
    workpaper_id: UUID
    title: str
    kind: Literal["control_deficiency", "misstatement", "compliance", "other"]
    coso_component: str | None
    citation_ids: tuple[UUID, ...]
    why_surfaced: str | None = None
    agent_run_id: UUID | None = None


@dataclass(frozen=True)
class Finding:
    id: UUID
    issue_id: UUID
    ref: str
    title: str
    kind: str
    route: str
    deficiency_status: str | None
    severity_proposed: str | None
    severity_concluded: str | None
    coso_component: str | None
    created_by_name: str
    created_at: datetime
    why_surfaced: str | None
    evaluation: dict[str, str]
    decision_card_id: UUID | None
    issue_status: str
    allowed_actions: tuple[str, ...]

    @property
    def band(self) -> str:
        return self.severity_concluded or self.severity_proposed or "not_a_deficiency"


@dataclass(frozen=True)
class FindingsPage:
    rows: list[Finding]
    counts: dict[str, int]
    awaiting_decision: int


async def _engagement(tenant: TenantContext, work_item_id: UUID) -> UUID:
    found = await work_item_engagement(tenant, work_item_id)
    if found is None:
        raise NotFound("work_item")
    return found


async def record_finding(ctx: AuthContext, work_item_id: UUID, new: NewFinding) -> Finding:
    """`POST …/findings` (the route authorised `finding.create`)."""
    engagement_id = await _engagement(ctx.tenant, work_item_id)
    agent = ctx.tenant.actor_kind == "agent"
    if agent:
        if new.agent_run_id is None or not new.citation_ids:
            raise UncitedFinding
        verified = await verified_citation_ids(ctx.tenant, "agent_run", [new.agent_run_id])
        live = {c for ids in verified.values() for c in ids}
        if not set(new.citation_ids) <= live:
            raise UncitedFinding
    issue_id = await create_issue(
        ctx,
        record_type="workpaper",
        record_id=new.workpaper_id,
        kind="exception",
        priority="medium",
        title=new.title.strip(),
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=(),
        work_item_id=work_item_id,
    )
    sealed = (
        None
        if new.why_surfaced is None
        else await seal(ctx.tenant_id, new.why_surfaced.encode(), _FINGERPRINT)
    )
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        number = (
            await tx.session.execute(
                text("SELECT count(*) + 1 FROM audit_findings WHERE work_item_id = :w"),
                {"w": work_item_id},
            )
        ).scalar_one()
        finding_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO audit_findings (tenant_id, engagement_id, work_item_id, "
                    "issue_id, ref, kind, title, coso_component, why_surfaced_sealed, "
                    "created_by_kind, agent_run_id) VALUES (:t, :e, :w, :i, :ref, :k, :title, "
                    ":coso, :why, :by, :run) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "i": issue_id,
                    "ref": f"F-{number:02d}",
                    "k": new.kind,
                    "title": new.title.strip(),
                    "coso": new.coso_component,
                    "why": sealed,
                    "by": "agent" if agent else "human",
                    "run": new.agent_run_id if agent else None,
                },
            )
        ).scalar_one()
        tx.record(
            "audit_finding.recorded",
            target=Target(TARGET, finding_id),
            after=Ref(issue=issue_id),  # who: the event's own actor (Ref holds identifiers only)
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await finding(ctx, finding_id)


_FINDINGS: Final = (
    "SELECT f.id, f.engagement_id, f.work_item_id, f.issue_id, f.ref, f.kind, f.route, "
    "f.title, f.coso_component, f.why_surfaced_sealed, f.created_by_kind, f.evaluation, "
    "f.created_at, d.status AS deficiency_status, d.severity_proposed, d.severity_concluded, "
    "d.decision_card_id FROM audit_findings f LEFT JOIN deficiencies d ON d.finding_id = f.id "
)
_FINDINGS_OF: Final = _FINDINGS + "WHERE f.work_item_id = :w ORDER BY f.ref"
_FINDING: Final = _FINDINGS + "WHERE f.id = :id"


async def _rows(ctx: AuthContext, rows: Sequence[RowMapping]) -> list[Finding]:
    if not rows:
        return []
    actions = await _actions(ctx, rows[0]["engagement_id"])
    out: list[Finding] = []
    for r in rows:
        issue = await issue_row(ctx.tenant, r["issue_id"])
        why = (
            None
            if r["why_surfaced_sealed"] is None
            else (
                await open_sealed(ctx.tenant_id, r["why_surfaced_sealed"], _FINGERPRINT)
            ).decode()
        )
        out.append(
            Finding(
                id=r["id"],
                issue_id=r["issue_id"],
                ref=r["ref"],
                title=r["title"],
                kind=r["kind"],
                route=r["route"],
                deficiency_status=r["deficiency_status"],
                severity_proposed=r["severity_proposed"],
                severity_concluded=r["severity_concluded"],
                coso_component=r["coso_component"],
                created_by_name="Accrued Agent" if r["created_by_kind"] == "agent" else "",
                created_at=r["created_at"],
                why_surfaced=why,
                evaluation={
                    str(k): str(v) for k, v in cast(dict[str, object], r["evaluation"]).items()
                },
                decision_card_id=r["decision_card_id"],
                issue_status=issue.status,
                allowed_actions=actions,
            )
        )
    return out


async def _actions(ctx: AuthContext, engagement_id: UUID) -> tuple[str, ...]:
    ref = await get_ref(ctx, engagement_id)
    can = await allowed_actions(ctx, ref.resource(), _ACTIONS)
    return tuple(a for a in _ACTIONS if a in can)


async def findings_of(
    ctx: AuthContext, work_item_id: UUID, *, hide_concluded: bool = False
) -> FindingsPage:
    """`GET …/findings` (the route authorised `finding.read`): the bands foot to the rows."""
    await _engagement(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(text(_FINDINGS_OF), {"w": work_item_id})).mappings().all()
    found = await _rows(ctx, rows)
    counts: dict[str, int] = dict.fromkeys(BANDS, 0)
    for f in found:
        counts[f.band] += 1
    awaiting = sum(1 for f in found if f.deficiency_status == "proposed")
    if hide_concluded:
        found = [f for f in found if f.deficiency_status not in ("concluded", "communicated")]
    return FindingsPage(found, counts, awaiting)


async def finding(ctx: AuthContext, finding_id: UUID) -> Finding:
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(text(_FINDING), {"id": finding_id})).mappings().first()
    if r is None:
        raise NotFound(TARGET)
    return (await _rows(ctx, [r]))[0]


async def work_item_of(tenant: TenantContext, finding_id: UUID) -> UUID:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text("SELECT work_item_id FROM audit_findings WHERE id = :id"), {"id": finding_id}
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound(TARGET)
    return found


async def move(
    ctx: AuthContext, finding_id: UUID, to: Literal["resolved", "not_applicable"]
) -> Finding:
    """Resolve or mark not applicable, through the finding's issue (the matrix refuses agents)."""
    found = await finding(ctx, finding_id)
    issue = await issue_row(ctx.tenant, found.issue_id)
    await move_issue(ctx, found.issue_id, to, issue.version)
    return await finding(ctx, finding_id)


async def to_deficiency(ctx: AuthContext, finding_id: UUID) -> Finding:
    """A control finding becomes a Proposed deficiency; the severity is the partner's card."""
    work_item = await work_item_of(ctx.tenant, finding_id)
    engagement_id = await _engagement(ctx.tenant, work_item)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE audit_findings SET route = 'converted_to_deficiency', "
                    "version = version + 1 WHERE id = :id AND route = 'under_evaluation' "
                    "RETURNING id"
                ),
                {"id": finding_id},
            )
        ).first()
        if moved is None:
            raise FindingMoved
        await tx.session.execute(
            text(
                "INSERT INTO deficiencies (tenant_id, engagement_id, work_item_id, finding_id, "
                "status) VALUES (:t, :e, :w, :f, 'proposed')"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "w": work_item, "f": finding_id},
        )
        tx.record(
            "audit_finding.converted",
            target=Target(TARGET, finding_id),
            # the route (deficiency) is the row's; Ref holds identifiers only
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await finding(ctx, finding_id)


async def to_misstatement(
    ctx: AuthContext,
    finding_id: UUID,
    *,
    type_: Literal["factual", "judgmental", "projected"],
    amount: Decimal | None,
    column_set: Literal["ebp_net_assets", "commercial"],
) -> UUID:
    """A misstatement from the finding: factual or judgmental with its amount; projected only from
    sampling's projection (422 `projection_unavailable` until it is exposed)."""
    if type_ == "projected" or amount is None or amount == 0:
        raise (
            ProjectionUnavailable
            if type_ == "projected"
            else DomainInvalid(facts={"field": "amount"})
        )
    work_item = await work_item_of(ctx.tenant, finding_id)
    engagement_id = await _engagement(ctx.tenant, work_item)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE audit_findings SET route = 'converted_to_misstatement', "
                    "version = version + 1 WHERE id = :id AND route = 'under_evaluation' "
                    "RETURNING id"
                ),
                {"id": finding_id},
            )
        ).first()
        if moved is None:
            raise FindingMoved
        number = (
            await tx.session.execute(
                text("SELECT count(*) + 1 FROM audit_misstatements WHERE work_item_id = :w"),
                {"w": work_item},
            )
        ).scalar_one()
        misstatement_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO audit_misstatements (tenant_id, engagement_id, work_item_id, "
                    "finding_id, ref, type, status, amount, column_set) VALUES (:t, :e, :w, :f, "
                    ":ref, :ty, 'confirmed', :a, :cs) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item,
                    "f": finding_id,
                    "ref": f"M-{number}",
                    "ty": type_,
                    "a": amount,
                    "cs": column_set,
                },
            )
        ).scalar_one()
        tx.record(
            "audit_finding.converted",
            target=Target(TARGET, finding_id),
            after=Ref(misstatement=misstatement_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return misstatement_id


AUDIT_KINDS: Final = frozenset({TARGET})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text("SELECT id, engagement_id FROM audit_findings WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}
