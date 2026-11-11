"""K-1 activities and treatments (T-04-T36; SPEC-649 §3.7 AC-7.1 to AC-7.6; TXI-02 a to e;
DEC-84, DEC-88, DEC-4309).

- **Activities.** A K-1 activity is one K-1 received on a return: from TXP-12's hand-off of the
  issuing partnership's package (`activity_from_handoff`; DEC-88: the values are copied at
  release, drafts never reach a portal) or a third-party K-1 a person uploads
  (`activity_from_upload`). The link to the source package is shown only to a person who can read
  both engagements; a wall on either side hides it (AC-7.6).
- **Treatments.** Up to eight per activity, one per kind, with the line they treat, the resolved
  treatment (facts from code; the agent's `k1_treatments` mode proposes, T-04-T38), SALY from the
  prior-year return's activity for the same issuer, and `changed_vs_prior` when the resolved
  treatment differs from SALY (TXI-02 c). Status is a projection of `k1_treatment_events`
  (insert-only); the row caches it.
- **Approval** (AC-7.3): the agent's proposal approved through SHL-10 (`proposal.approve`), then
  the applier (`apply_approved_treatments`) approves each proposed row for the person who decided,
  only if they hold `k1_treatment.approve` on the engagement (a preparer cannot,
  `level_not_permitted`), one `approved` event per row.
- **Override** (AC-7.4): a person with `k1_treatment.override` sets the client's treatment with a
  required reason (422 `reason_required`), sealed; the row reads "Overridden".
- **Release** (AC-7.5, DEC-84): `k1_package.released` marks each receiving activity released and
  diffs the draft's box lines against the hand-off's final values. An approved treatment whose
  boxes moved is never edited: it goes stale (`went_stale`) and is re-proposed (`reproposed`, back
  to Proposed for the reviewer), each an event.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import OutboxEvent, Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    could,
    display_names,
    engagement_resource,
    member_could,
)

READ: Final = "k1_treatment.read"
APPROVE: Final = "k1_treatment.approve"
OVERRIDE: Final = "k1_treatment.override"
KINDS: Final = (
    "passive_nonpassive",
    "ptp",
    "qbi_199a",
    "niit",
    "basis_at_risk",
    "state_sourcing",
    "ptet_credits",
    "tax_exempt_interest",
)
# The K-1 line each kind treats (Form 1065 Schedule K-1), as TXI-02's Line column reads it.
LINE_OF_KIND: Final[Mapping[str, str]] = {
    "passive_nonpassive": "Box 2",
    "ptp": "Item D",
    "qbi_199a": "Box 20Z",
    "niit": "Box 20Y",
    "basis_at_risk": "Item L",
    "state_sourcing": "State K-1",
    "ptet_credits": "Box 13",
    "tax_exempt_interest": "Box 18A",
}
# The boxes a kind's treatment rests on: a release that moves one makes the treatment stale.
BOXES_OF_KIND: Final[Mapping[str, frozenset[str]]] = {
    "passive_nonpassive": frozenset({"1", "2", "3"}),
    "ptp": frozenset({"D"}),
    "qbi_199a": frozenset({"1", "2", "20Z"}),
    "niit": frozenset({"2", "5", "6a", "20Y"}),
    "basis_at_risk": frozenset({"L", "K", "19A", "1", "2"}),
    "state_sourcing": frozenset({"state"}),
    "ptet_credits": frozenset({"13", "state"}),
    "tax_exempt_interest": frozenset({"18A"}),
}


class ReasonRequired(DomainInvalid):
    """An override names its reason (AC-7.4)."""

    code: ClassVar[str] = "reason_required"


class StaleTreatment(DomainConflict):
    code: ClassVar[str] = "stale_version"


class LevelNotPermitted(DomainForbidden):
    code: ClassVar[str] = "level_not_permitted"


@dataclass(frozen=True)
class TreatmentView:
    id: UUID
    kind: str
    line: str
    treatment: str
    status: str
    changed_vs_year: int | None
    decided_by_name: str | None
    version: int
    proposal_id: UUID | None


@dataclass(frozen=True)
class ActivityView:
    id: UUID
    label: str
    status: str
    released_on: datetime | None
    treatments: list[TreatmentView]
    pending_proposal_id: UUID | None
    source_package_id: UUID | None  # shown only with both engagements readable (DEC-88)


_ACTIVITIES_OF_RETURN = text(
    "SELECT a.id, a.tax_return_id, a.engagement_id, a.issuer_name, a.issuer_form, "
    "a.ownership_pct, a.source_package_id, a.k1_state, a.released_at, r.tax_year "
    "FROM k1_activities a JOIN tax_returns r ON r.work_item_id = a.tax_return_id "
    "WHERE a.tax_return_id = :r ORDER BY a.issuer_name, a.id"
)
_ACTIVITY = text(
    "SELECT a.id, a.tax_return_id, a.engagement_id, a.issuer_name, a.issuer_form, "
    "a.ownership_pct, a.source_package_id, a.k1_state, a.released_at, r.tax_year "
    "FROM k1_activities a JOIN tax_returns r ON r.work_item_id = a.tax_return_id "
    "WHERE a.id = :a"
)
_TREATMENTS = text(
    "SELECT id, k1_activity_id, kind, resolved, prior_year, changed_vs_prior, status, "
    "override_value, decided_by, proposal_id, version_no FROM k1_treatments "
    "WHERE k1_activity_id = ANY(:ids) ORDER BY k1_activity_id"
)
_PACKAGE_RETURN = text("SELECT work_item_id FROM k1_packages WHERE id = :p")


def _value_of(raw: object) -> str | None:
    if isinstance(raw, dict):
        found = cast(dict[str, object], raw)
        value = found.get("v", found.get("value"))
        return None if value is None else str(value)
    return None


def _saly_year(prior: object) -> int | None:
    """The SALY year a changed treatment compares with ("Changed vs 2024")."""
    if not isinstance(prior, dict):
        return None
    year = cast(dict[str, object], prior).get("year")
    return int(str(year)) if year else None


def treatment_text(resolved: object, override: object) -> str:
    return _value_of(override) or _value_of(resolved) or "Default"


def changed(resolved: object, prior: object) -> bool:
    """`changed_vs_prior`: the resolved treatment differs from SALY (no SALY: unchanged)."""
    before = _value_of(prior)
    return before is not None and before != _value_of(resolved)


async def _authorised(ctx: AuthContext, return_id: UUID) -> UUID:
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")  # INV-4: no portal principal reads a K-1 activity
    ref = await get_ref(ctx, engagement)
    await authorise(ctx, READ, ref.resource())
    return engagement


async def _source_visible(ctx: AuthContext, package_id: UUID | None) -> UUID | None:
    """DEC-88: the source package only when the person can read the issuing engagement too."""
    if package_id is None:
        return None
    async with tenant_session(ctx.tenant) as session:
        issuing = await session.scalar(_PACKAGE_RETURN, {"p": package_id})
    if issuing is None:
        return None
    engagement = await work_item_engagement(ctx.tenant, cast(UUID, issuing))
    if engagement is None:
        return None
    try:
        ref = await get_ref(ctx, engagement)  # a wall answers 404
    except NotFound:
        return None
    if not await could(ctx, ctx.user_id, "engagement.read", ref.resource()):
        return None
    return package_id


async def _views(
    ctx: AuthContext, session: AsyncSession, rows: Sequence[Row[Any]]
) -> list[ActivityView]:
    ids = [r.id for r in rows]
    treatments: Sequence[Row[Any]] = (
        (await session.execute(_TREATMENTS, {"ids": ids})).all() if ids else []
    )
    names = await display_names(sorted({t.decided_by for t in treatments if t.decided_by}))
    by_activity: dict[UUID, list[TreatmentView]] = {}
    for t in treatments:
        by_activity.setdefault(t.k1_activity_id, []).append(
            TreatmentView(
                id=t.id,
                kind=t.kind,
                line=LINE_OF_KIND.get(str(t.kind), str(t.kind)),
                treatment=treatment_text(t.resolved, t.override_value),
                status=t.status,
                changed_vs_year=_saly_year(t.prior_year) if t.changed_vs_prior else None,
                decided_by_name=names.get(t.decided_by) if t.decided_by else None,
                version=int(t.version_no),
                proposal_id=t.proposal_id,
            )
        )
    out: list[ActivityView] = []
    for r in rows:
        mine = sorted(by_activity.get(r.id, []), key=lambda v: KINDS.index(v.kind))
        pending = next(
            (v.proposal_id for v in mine if v.status == "proposed" and v.proposal_id), None
        )
        pct = r.ownership_pct
        share = f" · {Decimal(pct).normalize():f}%" if pct is not None else ""
        out.append(
            ActivityView(
                id=r.id,
                label=f"Schedule K-1 (Form {r.issuer_form}) · {r.issuer_name}{share}",
                status=r.k1_state,
                released_on=r.released_at,
                treatments=mine,
                pending_proposal_id=pending,
                source_package_id=await _source_visible(ctx, r.source_package_id),
            )
        )
    return out


async def list_k1_activities(ctx: AuthContext, return_id: UUID) -> list[ActivityView]:
    await _authorised(ctx, return_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ACTIVITIES_OF_RETURN, {"r": return_id})).all()
        return await _views(ctx, session, rows)


async def get_k1_activity(ctx: AuthContext, activity_id: UUID) -> ActivityView:
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ACTIVITY, {"a": activity_id})).all()
    if not rows:
        raise NotFound("k1_activity")
    await _authorised(ctx, rows[0].tax_return_id)
    async with tenant_session(ctx.tenant) as session:
        return (await _views(ctx, session, rows))[0]


async def activity_of_treatment(ctx: AuthContext, treatment_id: UUID) -> UUID:
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT k1_activity_id FROM k1_treatments WHERE id = :t"), {"t": treatment_id}
        )
    if found is None:
        raise NotFound("k1_treatment")
    return cast(UUID, found)


# --- override -------------------------------------------------------------------------------

_TREATMENT = text(
    "SELECT t.id, t.engagement_id, t.tax_return_id, t.kind, t.status, t.version_no "
    "FROM k1_treatments t WHERE t.id = :t FOR UPDATE"
)
_OVERRIDE = text(
    "UPDATE k1_treatments SET status = 'overridden', override_value = CAST(:value AS jsonb), "
    "override_reason_sealed = :reason, decided_by = :by, decided_at = clock_timestamp(), "
    "version_no = version_no + 1, updated_at = clock_timestamp() WHERE id = :t "
    "RETURNING version_no"
)
_EVENT = text(
    "INSERT INTO k1_treatment_events (tenant_id, engagement_id, tax_return_id, treatment_id, "
    "event, actor_kind, actor_id, proposal_id, reason_sealed) VALUES (:t, :e, :r, :tr, :event, "
    ":kind, :actor, :proposal, :reason)"
)


async def override_treatment(
    ctx: AuthContext, treatment_id: UUID, value: str, reason: str, seen_version: int
) -> int:
    """AC-7.4: the person's own treatment with a required reason; answers the new version."""
    if not reason.strip():
        raise ReasonRequired
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT engagement_id FROM k1_treatments WHERE id = :t"), {"t": treatment_id}
            )
        ).first()
    if found is None or ctx.client:
        raise NotFound("k1_treatment")
    ref = await get_ref(ctx, found.engagement_id)
    await authorise(ctx, OVERRIDE, ref.resource())
    sealed = await seal(ctx.tenant_id, reason.strip().encode(), "tax.k1_treatment.override")
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_TREATMENT, {"t": treatment_id})).one()
        if int(row.version_no) != seen_version:
            raise StaleTreatment
        version = cast(
            int,
            await tx.session.scalar(
                _OVERRIDE,
                {
                    "value": json.dumps({"t": "text", "v": value}),
                    "reason": sealed,
                    "by": ctx.user_id,
                    "t": treatment_id,
                },
            ),
        )
        await tx.session.execute(
            _EVENT,
            {
                "t": ctx.tenant_id,
                "e": row.engagement_id,
                "r": row.tax_return_id,
                "tr": treatment_id,
                "event": "overridden",
                "kind": "human",
                "actor": str(ctx.user_id),
                "proposal": None,
                "reason": sealed,
            },
        )
        tx.record(
            "k1_treatment.overridden",
            target=Target("k1_treatment", treatment_id),
            after=Ref(version=version),
            scope=Scope(engagement_id=row.engagement_id),
        )
    return version


# --- approval through the proposal applier --------------------------------------------------

_PROPOSED_ROWS = text(
    "SELECT id, engagement_id, tax_return_id FROM k1_treatments WHERE id = ANY(:ids) "
    "AND status = 'proposed' FOR UPDATE"
)
_APPROVE = text(
    "UPDATE k1_treatments SET status = 'approved', decided_by = :by, "
    "decided_at = clock_timestamp(), proposal_id = :p, version_no = version_no + 1, "
    "updated_at = clock_timestamp() WHERE id = :t"
)


async def apply_approved_treatments(
    tenant: TenantContext, proposal_id: UUID, approver: UUID | None, treatment_ids: Sequence[UUID]
) -> int:
    """AC-7.3: each proposed row named by the approved proposal is approved for the person who
    approved it, when they hold `k1_treatment.approve` on the engagement; answers the count."""
    if approver is None or not treatment_ids:
        return 0
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")
    async with tenant_session(system) as session:
        engagement = await session.scalar(
            text("SELECT engagement_id FROM k1_treatments WHERE id = ANY(:ids) LIMIT 1"),
            {"ids": list(treatment_ids)},
        )
    if engagement is None:
        return 0
    resource = await engagement_resource(system, cast(UUID, engagement))
    allowed = await member_could(tenant.tenant_id, approver, APPROVE, resource)
    if not allowed:
        raise LevelNotPermitted
    async with uow(system) as tx:
        rows = (await tx.session.execute(_PROPOSED_ROWS, {"ids": list(treatment_ids)})).all()
        for row in rows:
            await tx.session.execute(_APPROVE, {"by": approver, "p": proposal_id, "t": row.id})
            await tx.session.execute(
                _EVENT,
                {
                    "t": tenant.tenant_id,
                    "e": row.engagement_id,
                    "r": row.tax_return_id,
                    "tr": row.id,
                    "event": "approved",
                    "kind": "human",
                    "actor": str(approver),
                    "proposal": proposal_id,
                    "reason": None,
                },
            )
        tx.record(
            "k1_treatment.approved",
            target=Target("proposal", proposal_id),
            after=Ref(rows=len(rows), by=approver),
            scope=Scope(engagement_id=cast(UUID, engagement)),
        )
    return len(rows)


# --- SALY ------------------------------------------------------------------------------------

_PRIOR = text(
    "SELECT t.kind, t.resolved, t.override_value, pr.tax_year FROM k1_treatments t "
    "JOIN k1_activities pa ON pa.id = t.k1_activity_id "
    "JOIN tax_returns pr ON pr.work_item_id = pa.tax_return_id "
    "JOIN tax_returns cr ON cr.client_entity_id = pr.client_entity_id AND cr.form = pr.form "
    "JOIN k1_activities ca ON ca.tax_return_id = cr.work_item_id "
    "WHERE ca.id = :a AND pa.issuer_name = ca.issuer_name AND pr.tax_year = cr.tax_year - 1"
)
_SALY = text(
    "UPDATE k1_treatments SET prior_year = CAST(:prior AS jsonb), changed_vs_prior = :changed, "
    "updated_at = clock_timestamp() WHERE k1_activity_id = :a AND kind = :kind"
)


async def refresh_saly(tenant: TenantContext, activity_id: UUID) -> int:
    """SALY from the prior-year return's activity for the same issuer, and `changed_vs_prior`."""
    async with tenant_session(tenant) as session:
        prior = (await session.execute(_PRIOR, {"a": activity_id})).all()
        current = {
            r.kind: r.resolved
            for r in (
                await session.execute(
                    text("SELECT kind, resolved FROM k1_treatments WHERE k1_activity_id = :a"),
                    {"a": activity_id},
                )
            ).all()
        }
    if not prior:
        return 0
    async with uow(tenant) as tx:
        for p in prior:
            saly = {"v": _value_of(p.override_value) or _value_of(p.resolved), "year": p.tax_year}
            await tx.session.execute(
                _SALY,
                {
                    "prior": json.dumps(saly),
                    "changed": changed(current.get(p.kind), saly),
                    "a": activity_id,
                    "kind": p.kind,
                },
            )
        tx.record(
            "k1_activity.saly_refreshed",
            target=Target("k1_activity", activity_id),
            after=Ref(rows=len(prior)),
        )
    return len(prior)


# --- activities from a hand-off or an upload -------------------------------------------------

_HANDOFF = text(
    "SELECT h.package_id, h.target_work_item_id, p.form, p.tax_year, p.work_item_id AS issuing "
    "FROM k1_handoffs h JOIN k1_packages p ON p.id = h.package_id WHERE h.id = :h"
)
_INSERT_ACTIVITY = text(
    "INSERT INTO k1_activities (tenant_id, engagement_id, tax_return_id, issuer_name, "
    "issuer_form, recipient_tsj, ownership_pct, source_package_id, k1_state, "
    "source_evidence_version_ids, content_hash) VALUES (:t, :e, :r, :issuer, :form, :tsj, :pct, "
    ":package, 'draft_pre_release', :evidence, :hash) "
    "ON CONFLICT (tax_return_id, source_package_id) WHERE source_package_id IS NOT NULL "
    "DO NOTHING RETURNING id"
)


def _hash(*parts: object) -> str:
    return hashlib.sha256(json.dumps([str(p) for p in parts]).encode()).hexdigest()


async def activity_from_handoff(
    tenant: TenantContext, handoff_id: UUID, issuer_name: str, ownership_pct: Decimal | None
) -> UUID | None:
    """The receiving return's activity for a TXP-12 hand-off (DEC-88), once per package."""
    async with tenant_session(tenant) as session:
        found = (await session.execute(_HANDOFF, {"h": handoff_id})).first()
    if found is None:
        raise NotFound("k1_handoff")
    engagement = await work_item_engagement(tenant, found.target_work_item_id)
    if engagement is None:
        raise NotFound("tax_return")
    async with uow(tenant) as tx:
        activity = await tx.session.scalar(
            _INSERT_ACTIVITY,
            {
                "t": tenant.tenant_id,
                "e": engagement,
                "r": found.target_work_item_id,
                "issuer": issuer_name,
                "form": found.form,
                "tsj": "T",
                "pct": ownership_pct,
                "package": found.package_id,
                "evidence": [],
                "hash": _hash(found.package_id, issuer_name, ownership_pct),
            },
        )
        if activity is not None:
            tx.record(
                "k1_activity.created",
                target=Target("k1_activity", cast(UUID, activity)),
                after=Ref(package=found.package_id),
                scope=Scope(engagement_id=engagement),
            )
    return cast(UUID | None, activity)


async def activity_from_upload(
    ctx: AuthContext,
    return_id: UUID,
    *,
    issuer_name: str,
    issuer_form: str,
    evidence_version_id: UUID,
    ownership_pct: Decimal | None = None,
) -> UUID:
    """A third-party K-1 a person uploaded: no source package; the evidence is the source."""
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")
    ref = await get_ref(ctx, engagement)
    await authorise(ctx, "k1_treatment.resolve", ref.resource())
    async with uow(ctx.tenant) as tx:
        activity = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_ACTIVITY,
                {
                    "t": ctx.tenant_id,
                    "e": engagement,
                    "r": return_id,
                    "issuer": issuer_name,
                    "form": issuer_form,
                    "tsj": "T",
                    "pct": ownership_pct,
                    "package": None,
                    "evidence": [evidence_version_id],
                    "hash": _hash(evidence_version_id, issuer_name, ownership_pct),
                },
            ),
        )
        tx.record(
            "k1_activity.created",
            target=Target("k1_activity", activity),
            after=Ref(evidence=evidence_version_id),
            scope=Scope(engagement_id=engagement),
        )
    return activity


# --- the release consumer (DEC-84) -----------------------------------------------------------

_DRAFT_LINES = text(
    "SELECT box_code, amount FROM k1_box_lines WHERE package_id = :p AND document_kind = 'k1'"
)
_FINAL = text(
    "SELECT final_values FROM k1_handoffs WHERE package_id = :p AND final_values IS NOT NULL "
    "ORDER BY shared_at DESC LIMIT 1"
)
_RECEIVING = text(
    "SELECT id, engagement_id, tax_return_id FROM k1_activities WHERE source_package_id = :p"
)
_RELEASE = text(
    "UPDATE k1_activities SET k1_state = 'released', released_at = clock_timestamp(), "
    "version_no = version_no + 1, updated_at = clock_timestamp() WHERE id = :a "
    "AND k1_state = 'draft_pre_release'"
)
_APPROVED_OF = text(
    "SELECT id, kind FROM k1_treatments WHERE k1_activity_id = :a AND status = 'approved' "
    "FOR UPDATE"
)
_REPROPOSE = text(
    "UPDATE k1_treatments SET status = 'proposed', decided_by = NULL, decided_at = NULL, "
    "version_no = version_no + 1, updated_at = clock_timestamp() WHERE id = :t"
)


def moved_boxes(draft: Mapping[str, Decimal], final: Mapping[str, Decimal]) -> frozenset[str]:
    """The boxes whose amount differs between the draft and the final K-1."""
    keys = set(draft) | set(final)
    return frozenset(k for k in keys if draft.get(k) != final.get(k))


def stale_kinds(moved: frozenset[str], approved: Sequence[str]) -> list[str]:
    return [k for k in approved if BOXES_OF_KIND.get(k, frozenset()) & moved]


async def on_package_released(event: OutboxEvent) -> None:
    """AC-7.5: release each receiving activity; re-propose every approved treatment whose boxes
    moved between the draft and the final K-1 (never edit it)."""
    package = UUID(str(event.payload["package_id"]))
    tenant = TenantContext(event.tenant_id, "system", "tax:k1-release")
    async with tenant_session(tenant) as session:
        draft = {
            str(r.box_code): Decimal(r.amount)
            for r in (await session.execute(_DRAFT_LINES, {"p": package})).all()
        }
        raw = await session.scalar(_FINAL, {"p": package})
        receiving = (await session.execute(_RECEIVING, {"p": package})).all()
    final_raw = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    final = {str(k): Decimal(str(v)) for k, v in final_raw.items() if v is not None}
    moved: frozenset[str] = moved_boxes(draft, final) if final else frozenset[str]()
    for activity in receiving:
        async with uow(tenant) as tx:
            await tx.session.execute(_RELEASE, {"a": activity.id})
            approved = (await tx.session.execute(_APPROVED_OF, {"a": activity.id})).all()
            stale = set(stale_kinds(moved, [a.kind for a in approved]))
            for row in approved:
                if row.kind not in stale:
                    continue
                await tx.session.execute(_REPROPOSE, {"t": row.id})
                for name in ("went_stale", "reproposed"):
                    await tx.session.execute(
                        _EVENT,
                        {
                            "t": event.tenant_id,
                            "e": activity.engagement_id,
                            "r": activity.tax_return_id,
                            "tr": row.id,
                            "event": name,
                            "kind": "system",
                            "actor": "tax:k1-release",
                            "proposal": None,
                            "reason": None,
                        },
                    )
            tx.record(
                "k1_activity.released",
                target=Target("k1_activity", activity.id),
                after=Ref(moved=len(moved), reproposed=len(stale)),
                scope=Scope(engagement_id=activity.engagement_id),
            )
