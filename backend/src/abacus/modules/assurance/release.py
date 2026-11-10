"""Interim G8: the report released outside Accrued, recorded (A-01-T23; A-01 §3.5 Story 5.2;
DEC-83, DEC-590). PROTECTED (red path, chapter 03 §2.2).

While a firm's `assurance_release_mode` is `external` (the default; A-07 brings `in_app`), the
engagement partner records the date the report left the firm's own tool and whether there was a
report at all (AR-C 70 issues none):

- **Who.** `assurance.record_release`: the engagement partner only, with independence and a
  second factor verified in the last 15 minutes (a stale one is 403 `mfa_required`, DEC-547), a
  live person's own act (INV-1; the table's CHECK and insert trigger bind the row to the
  session's human actor; `assurance.release_recorded` is on the human-only register).
- **When.** `release_mode_in_app` (409) while the firm releases in Accrued; the date may not be
  after the firm's today (422 `release_date_future`) nor on or before the engagement's fiscal
  period end (422 `release_date_before_period_end`, DEC-598); the phase must be In review,
  Completion or Ready to release (409 `record_out_of_phase`: SPEC-314's G6 and G7 are registered
  for every firm, so an external-mode firm cannot record Ready to release, DEC-590), and a work
  item is released once.
- **What.** One insert-only row, the derived move to Released naming G8 (`advance_by_gate`, the
  person named), and the audit event, in one unit of work. The 60-day documentation clock reads
  the recorded date (AU-C 230).

The G8 provider registered for every firm is `g8` below: met by SPEC-314's in-app release or by
this record, whichever the firm used. Code records what a person states; it never decides.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance import completion
from abacus.modules.assurance.external_models import ExternalRelease, external_release_of
from abacus.modules.assurance.phase import advance_by_gate
from abacus.modules.assurance.record_auth import authorise_record, fresh_mfa_at
from abacus.modules.engagements.api import (
    GateFact,
    assurance_item,
    engagement_hold_facts,
    engagement_metadata,
    lock_assurance_item,
    lock_ref,
)
from abacus.modules.identity.api import AuthContext, SettingKey, stored_value
from abacus.modules.reporting.api import ApprovalRef, RenderOutcome

ACTION: Final = "assurance.record_release"
DOCUMENTATION_DAYS: Final = 60  # AU-C 230
ReleaseMode = Literal["external", "in_app"]
RELEASE_MODES: Final[tuple[str, ...]] = ("external", "in_app")
# The firm setting (A-01 §0): registered in the typed store, so only a firm admin with a fresh
# second factor changes it (`firm.manage_settings`), audited `firm_setting.updated`.
RELEASE_MODE_SETTING: Final = SettingKey(
    "defaults", "assurance_release_mode", "text", max_length=16, choices=RELEASE_MODES
)
# A release is recorded once fieldwork is behind the audit (DEC-590).
_RELEASABLE: Final = frozenset({"in_review", "completion", "ready_to_release"})


class ReleaseModeInApp(DomainConflict):
    """The firm releases reports in Accrued (`assurance_release_mode = in_app`): record mode is
    closed for release and archive."""

    code = "release_mode_in_app"


class ReleaseDateFuture(DomainInvalid):
    """The release date is after the firm's today."""

    code = "release_date_future"


class ReleaseDateBeforePeriodEnd(DomainInvalid):
    """The release date is on or before the engagement's fiscal period end: a report on a period
    is released after it closes (DEC-598)."""

    code = "release_date_before_period_end"


class RecordOutOfPhase(DomainConflict):
    """The audit's phase does not take this record: a release from In review to Ready to
    release, an archive once Released (`facts.phase`)."""

    code = "record_out_of_phase"


@dataclass(frozen=True)
class ReleaseRecord:
    work_item_id: UUID
    report_released_on: date
    report_kind: str
    phase: str
    archive_due_on: date
    recorded_at: datetime


async def release_mode(tenant: TenantContext) -> ReleaseMode:
    """The firm's `assurance_release_mode`; unset reads `external` (the default)."""
    value = await stored_value(tenant, "defaults", "assurance_release_mode")
    return "in_app" if value == "in_app" else "external"


async def require_external(tenant: TenantContext) -> None:
    if await release_mode(tenant) == "in_app":
        raise ReleaseModeInApp(facts={"mode": "in_app"})


async def record_release(
    ctx: AuthContext, work_item_id: UUID, released_on: date, report_kind: str
) -> ReleaseRecord:
    """Story 5.2: "Report released outside Accrued on Jul 29, 2026"."""
    if report_kind not in ("opinion", "no_report"):
        raise DomainInvalid("report_kind")
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise_record(ctx, ACTION, ref.resource())
        await require_external(ctx.tenant)
        if released_on > await clock.today(ctx.tenant):
            raise ReleaseDateFuture(facts={"report_released_on": released_on.isoformat()})
        period = (await engagement_metadata(ctx, found.engagement_id)).engagement
        if released_on <= period.fiscal_period_end:
            raise ReleaseDateBeforePeriodEnd(
                facts={"fiscal_period_end": period.fiscal_period_end.isoformat()}
            )
        item = await lock_assurance_item(tx, work_item_id)
        if item.phase not in _RELEASABLE:
            raise RecordOutOfPhase(facts={"phase": item.phase})
        if await external_release_of(tx.session, item.engagement_id) is not None:
            raise RecordOutOfPhase(facts={"phase": item.phase})
        mfa_at = fresh_mfa_at(ctx)
        row = ExternalRelease(
            work_item_id=item.work_item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=item.engagement_id,
            report_released_on=released_on,
            report_kind=report_kind,
            recorded_by=ctx.user_id,
            actor_kind="human",
            mfa_at=mfa_at,
        )
        tx.session.add(row)
        await advance_by_gate(tx, ctx.tenant, item.engagement_id, "released", "G8", ctx.user_id)
        tx.record(
            "assurance.release_recorded",
            target=Target("engagement", item.engagement_id),
            after=Ref(
                work_item=item.work_item_id,
                released_on=int(released_on.strftime("%Y%m%d")),
                no_report=int(report_kind == "no_report"),
                mfa_at=int(mfa_at.timestamp()),
            ),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=item.work_item_id),
        )
        await tx.session.refresh(row)
        return ReleaseRecord(
            item.work_item_id,
            released_on,
            report_kind,
            "released",
            released_on + timedelta(days=DOCUMENTATION_DAYS),
            row.recorded_at,
        )


async def g8(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G8 for every firm: SPEC-314's in-app release, or the external release record."""
    in_app = await completion.g8(tenant, engagement_id)
    if in_app.met:
        return in_app
    async with tenant_session(tenant) as session:
        recorded = await external_release_of(session, engagement_id)
    if recorded is not None:
        return GateFact(met=True, blockers=())
    return in_app


# =================================================================================================
# In-app G8: the release transaction (A-07-T30; A-07 F6; SPEC-644; DEC-3107). PROTECTED.
#
# While a firm releases in Accrued (`assurance_release_mode = in_app`, `audits.report_release`
# on), the engagement partner releases from AUD-24:
#
# 1. `request_release` (POST …/release, 202): a live person, the engagement partner alone, with a
#    second factor verified in the last 15 minutes (the matrix's `mfa_recent`, and the record's
#    own check), the gates as the dialog saw them (`seen_gate_hash`), an approved current report
#    version and its draft render. It issues an approval grant bound to (work item, report
#    version, draft hash, gate hash) and starts ReleaseWorkflow. A replay while that grant is
#    live, or after the release with the same Idempotency-Key, answers the same run; nothing is
#    issued twice.
# 2. ReleaseWorkflow (`release_workflow.py`): consumes the grant (the single gate), re-evaluates
#    G5-G7 and the also-required list (409 `gates_not_met`, `content_changed` on any change),
#    asks C11 for the final render (no watermark, the firm signature, the grant as its approval),
#    waits for the render job, then in ONE unit of work records `report_releases` (kind
#    `original`, the gate snapshot and its SHA-256, the final document version), freezes the
#    report (`released`), locks the C11 document, publishes the deliverables through C10 and
#    emits `report.released`. Any failure voids the grant and records nothing (RELEASE-001: only
#    this file writes `report_releases`).
#
# Code computes the gate facts; the EP decides. No agent, system or client principal releases
# (I-AGENT-NEVER): the matrix denies them, `authorise_record` refuses any non-person, the grant
# is a person's own decision, and the table's CHECK binds the row to a human actor.
# =================================================================================================

RELEASE_ACTION: Final = "report.release"
RELEASE_SUBJECT: Final = "audit_report_version"
GRANT_TTL: Final = timedelta(hours=1)  # the workflow consumes it within seconds
ALSO_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "fs_approved",
    "bring_down",
    "independence",
    "final_materiality",
    "governance_260",
)


class ReleaseModeExternal(DomainConflict):
    """The firm records releases made outside Accrued (`assurance_release_mode = external`)."""

    code = "release_mode_external"


class GatesNotMet(DomainConflict):
    """G5, G6, G7, the report's approval or an also-required item is not met
    (`facts.gates`: the identifiers that block)."""

    code = "gates_not_met"


class ContentChanged(DomainConflict):
    """What the dialog saw (`seen_gate_hash`) is not what the server computes now."""

    code = "content_changed"


class AlreadyReleased(DomainConflict):
    """The work item's original release exists (a reissue is A-07's later path)."""

    code = "already_released"


class ReleaseRefused(DomainConflict):
    """The release cannot proceed (`facts.reason`: grant_refused, render_failed)."""

    code = "release_refused"

    def __init__(self, reason: str) -> None:
        super().__init__(facts={"reason": reason})


@dataclass(frozen=True)
class AlsoRequired:
    key: str
    met: bool
    value: str | None = None


AlsoRequiredProvider = Callable[[TenantContext, UUID, UUID], Awaitable[AlsoRequired]]
_ALSO_REQUIRED: dict[str, AlsoRequiredProvider] = {}


def register_also_required(key: str, provider: AlsoRequiredProvider) -> None:
    """A provider of one also-required item (the module that owns its facts). An item with no
    provider is unmet (fail closed)."""
    if key not in ALSO_REQUIRED_KEYS:
        raise ValueError(f"unknown also-required item {key}")
    _ALSO_REQUIRED[key] = provider


@dataclass(frozen=True)
class GateCard:
    gate: str
    met: bool
    required: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseSnapshot:
    """Everything a release depends on, read at one point: the gate hash is its SHA-256."""

    work_item_id: UUID
    engagement_id: UUID
    gates: tuple[GateCard, ...]
    also_required: tuple[AlsoRequired, ...]
    report_id: UUID | None
    report_version_id: UUID | None
    report_version_hash: str | None
    report_status: str
    report_approved: bool
    report_date: date | None
    city: str | None

    @property
    def blockers(self) -> tuple[str, ...]:
        out = [g.gate for g in self.gates if g.required and not g.met]
        if not self.report_approved:
            out.append("report_not_approved")
        out.extend(f"also_required:{a.key}" for a in self.also_required if not a.met)
        return tuple(out)

    def canonical(self) -> dict[str, object]:
        return {
            "work_item_id": str(self.work_item_id),
            "gates": [
                {
                    "gate": g.gate,
                    "met": g.met,
                    "required": g.required,
                    "blockers": list(g.blockers),
                }
                for g in self.gates
            ],
            "also_required": [{"key": a.key, "met": a.met} for a in self.also_required],
            "report_version_id": None
            if self.report_version_id is None
            else str(self.report_version_id),
            "report_version_hash": self.report_version_hash,
            "report_approved": self.report_approved,
            "report_date": None if self.report_date is None else self.report_date.isoformat(),
        }

    @property
    def sha256(self) -> str:
        body = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()


_REPORT_ROW = text(
    "SELECT r.id, r.status, r.report_date, r.city, v.id AS version_id, v.content_hash "
    "FROM audit_reports r LEFT JOIN audit_report_versions v ON v.id = r.current_version_id "
    "WHERE r.work_item_id = :wi"
)
_RELEASE_ROW = text(
    "SELECT id, released_by, released_at, report_date, deliverable_ids, idempotency_key, "
    "final_document_version_id, gate_snapshot_sha256 FROM report_releases "
    "WHERE work_item_id = :wi AND kind = 'original'"
)


async def _report_approved(tenant: TenantContext, version_id: UUID, content_hash: str) -> bool:
    """The engagement partner's L4 sign-off on this report version, not stale (P-04 grammar)."""
    from abacus.modules.review.api import sign_off_states

    states = await sign_off_states(
        tenant, RELEASE_SUBJECT, [version_id], {version_id: content_hash}
    )
    return any(
        s.level == 4 and s.signed_by is not None and not s.stale
        for s in states.get(version_id, [])
    )


async def snapshot(tenant: TenantContext, work_item_id: UUID) -> ReleaseSnapshot:
    """G5 to G7 from their providers, the also-required list and the report, never the browser's
    values. A provider that fails leaves its item unmet."""
    from abacus.modules.assurance import gates as gate_providers

    found = await assurance_item(tenant, work_item_id)
    engagement_id = found.engagement_id
    cards: list[GateCard] = []
    for gate, provider in (
        ("G5", gate_providers.g5_facts),
        ("G6", gate_providers.in_app_g6),
        ("G7", gate_providers.in_app_g7),
    ):
        try:
            fact = await provider(tenant, engagement_id)
        except Exception:
            fact = GateFact(met=False, blockers=("gate_unavailable",))
        cards.append(GateCard(gate, fact.met, True, tuple(fact.blockers)))
    also: list[AlsoRequired] = []
    for key in ALSO_REQUIRED_KEYS:
        provider = _ALSO_REQUIRED.get(key)
        if provider is None:
            also.append(AlsoRequired(key, False))
            continue
        try:
            also.append(await provider(tenant, engagement_id, work_item_id))
        except Exception:
            also.append(AlsoRequired(key, False))
    async with tenant_session(tenant) as session:
        report = (await session.execute(_REPORT_ROW, {"wi": work_item_id})).first()
    approved = False
    if report is not None and report.version_id is not None:
        approved = await _report_approved(tenant, report.version_id, str(report.content_hash))
    return ReleaseSnapshot(
        work_item_id,
        engagement_id,
        tuple(cards),
        tuple(also),
        None if report is None else report.id,
        None if report is None else report.version_id,
        None if report is None else report.content_hash,
        "draft" if report is None else str(report.status),
        approved,
        None if report is None else report.report_date,
        None if report is None else report.city,
    )


@dataclass(frozen=True)
class ReleasedFacts:
    release_id: UUID
    released_by: UUID
    released_at: datetime
    report_date: date
    deliverable_ids: tuple[UUID, ...]
    idempotency_key: str | None
    final_document_version_id: UUID

    @property
    def documentation_completion_date(self) -> date:
        """AU-C 230: 60 days after the report release date."""
        return self.released_at.astimezone(clock.FIRM_ZONE).date() + timedelta(
            days=DOCUMENTATION_DAYS
        )


async def released(tenant: TenantContext, work_item_id: UUID) -> ReleasedFacts | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_RELEASE_ROW, {"wi": work_item_id})).first()
    if row is None:
        return None
    return ReleasedFacts(
        row.id,
        row.released_by,
        row.released_at,
        row.report_date,
        tuple(row.deliverable_ids or ()),
        row.idempotency_key,
        row.final_document_version_id,
    )


def grant_digest(work_item_id: UUID, version_id: UUID, draft_hash: str, gate_hash: str) -> str:
    """What the grant is bound to: this report version's draft, under these gate facts."""
    body = f"report.release:{work_item_id}:{version_id}:{draft_hash}:{gate_hash}"
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class ReleaseRequest:
    """ReleaseWorkflow's input, also the replay's answer: identifiers and hashes only."""

    tenant_id: str
    work_item_id: str
    engagement_id: str
    grant_id: str
    released_by: str
    report_version_id: str
    draft_document_id: str
    draft_hash: str
    gate_hash: str
    idempotency_key: str


def workflow_id(tenant_id: UUID, work_item_id: UUID, grant_id: UUID) -> str:
    """One run per decision; the database's one-original index keeps G8 single."""
    return f"release:{tenant_id}:{work_item_id}:{grant_id}"


async def request_release(
    ctx: AuthContext, work_item_id: UUID, seen_gate_hash: str, idempotency_key: str
) -> ReleaseRequest | ReleasedFacts:
    """AUD-24 c: issue the grant and start ReleaseWorkflow (the caller dispatches it after the
    unit of work commits). A replay answers the stored release or the same request."""
    from abacus.modules.identity.api import issue_grant
    from abacus.modules.reporting import api as c11

    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        resource = replace(ref.resource(), work_item_id=work_item_id)
        await authorise_record(ctx, RELEASE_ACTION, resource)
        mfa_at = fresh_mfa_at(ctx)
        if await release_mode(ctx.tenant) != "in_app":
            raise ReleaseModeExternal(facts={"mode": "external"})
        done = await released(ctx.tenant, work_item_id)
        if done is not None:
            if done.idempotency_key == idempotency_key:
                tx.record(
                    "report.release_replayed",
                    target=Target("report_release", done.release_id),
                    scope=Scope(engagement_id=found.engagement_id, work_item_id=work_item_id),
                )
                return done
            raise AlreadyReleased(facts={"release_id": str(done.release_id)})
        await lock_assurance_item(tx, work_item_id)  # one release request at a time
        snap = await snapshot(ctx.tenant, work_item_id)
        if snap.blockers:
            raise GatesNotMet(facts={"gates": ",".join(snap.blockers)})
        if snap.sha256 != seen_gate_hash:
            raise ContentChanged(facts={"gate_hash": snap.sha256})
        version_id = cast(UUID, snap.report_version_id)
        document_id = await c11.document_of_owner(
            ctx.tenant, c11.OwnerRef(RELEASE_SUBJECT, version_id), "audit_report"
        )
        latest = (
            None
            if document_id is None
            else await c11.latest_document_version(ctx.tenant, document_id)
        )
        if document_id is None or latest is None:
            raise GatesNotMet(facts={"gates": "report_not_rendered"})
        draft_hash = latest[1]
        digest = grant_digest(work_item_id, version_id, draft_hash, snap.sha256)
        now = await clock.now(ctx.tenant)
        # A fresh grant per decision: a spent grant is never reused, so a later attempt always
        # carries its own fresh-MFA decision (consume_grant answers True to a spent grant's own
        # consumer, which a reuse would turn into a release without one).
        grant_id = await issue_grant(
            tx,
            ctx,
            action=RELEASE_ACTION,
            resource=resource,
            subject=Target(RELEASE_SUBJECT, version_id),
            payload_sha256=digest,
            not_before=now,
            expires_at=now + GRANT_TTL,
        )
        tx.record(
            "report.release_requested",
            target=Target(RELEASE_SUBJECT, version_id),
            after=Ref(grant=grant_id, gate_hash=snap.sha256, mfa_at=int(mfa_at.timestamp())),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=work_item_id),
        )
    return ReleaseRequest(
        str(ctx.tenant_id),
        str(work_item_id),
        str(found.engagement_id),
        str(grant_id),
        str(ctx.user_id),
        str(version_id),
        str(document_id),
        draft_hash,
        snap.sha256,
        idempotency_key,
    )


# --- the workflow's steps (activities call these; release_workflow.py) ------------------------

# The approval the C11 provider confirms for a final render of `audit_report`: set only while
# `consume_and_render` runs, after the grant was consumed (notices/sending.py's pattern).
_approving: ContextVar[tuple[ApprovalRef, UUID] | None] = ContextVar(
    "report_release", default=None
)


async def report_release_approval(ref: ApprovalRef) -> tuple[UUID, str] | None:
    """C11's approval provider for `audit_report`: the consumed release grant's approver, for
    the draft hash it was bound to; None at any other time (a final render is the EP's)."""
    held = _approving.get()
    if held is None or held[0] != ref:
        return None
    return held[1], ref.content_hash


def _system(request: ReleaseRequest) -> TenantContext:
    return TenantContext(
        UUID(request.tenant_id),
        "system",
        f"release:{request.work_item_id}",
        on_behalf_of_user_id=UUID(request.released_by),
    )


async def consume_and_render(request: ReleaseRequest) -> int:
    """Consume the grant, re-check the gates, ask C11 for the final render. Answers the final
    version's number. Raises GatesNotMet, ContentChanged or ReleaseRefused."""
    from abacus.modules.identity.api import consume_grant
    from abacus.modules.reporting import api as c11

    tenant_id = UUID(request.tenant_id)
    work_item_id = UUID(request.work_item_id)
    version_id = UUID(request.report_version_id)
    digest = grant_digest(work_item_id, version_id, request.draft_hash, request.gate_hash)
    if not await consume_grant(tenant_id, UUID(request.grant_id), version_id, digest):
        raise ReleaseRefused("grant_refused")
    system = _system(request)
    snap = await snapshot(system, work_item_id)
    if snap.blockers:
        raise GatesNotMet(facts={"gates": ",".join(snap.blockers)})
    if snap.sha256 != request.gate_hash:
        raise ContentChanged(facts={"gate_hash": snap.sha256})
    approval = c11.ApprovalRef("report_release", UUID(request.grant_id), request.draft_hash)
    token = _approving.set((approval, UUID(request.released_by)))
    try:
        async with uow(system) as tx:
            ticket = await c11.render_final(
                tx,
                UUID(request.draft_document_id),
                approval,
                c11.Requester("human", user_id=UUID(request.released_by)),
            )
            tx.record(
                "report.final_render_requested",
                target=Target(RELEASE_SUBJECT, version_id),
                after=Ref(document=UUID(request.draft_document_id), version_no=ticket.version_no),
                scope=Scope(engagement_id=UUID(request.engagement_id), work_item_id=work_item_id),
            )
    finally:
        _approving.reset(token)
    return ticket.version_no


async def final_render(request: ReleaseRequest, version_no: int) -> RenderOutcome:
    """The final render job's outcome: the activity retries while it is queued or running."""
    from abacus.modules.reporting import api as c11

    return await c11.render_outcome(_system(request), UUID(request.draft_document_id), version_no)


async def _audiences(tenant: TenantContext, engagement_id: UUID) -> tuple[object, ...]:
    """The released report's audience: the engagement's client (C10 resolves its contacts)."""
    from abacus.modules.reporting import api as c11

    facts = await engagement_hold_facts(tenant, engagement_id)
    if facts is None:
        raise NotFound("engagement")
    return (c11.DeliverableAudience("client", facts.client_id),)


async def record_in_app_release(
    request: ReleaseRequest,
    final_version_id: UUID,
    evidence_version_id: UUID,
    render_hash: str,
    page_count: int,
) -> UUID:
    """The one unit of work (AUD-24 c → d): the gates once more at this sequence, then G8 —
    `report_releases`, the report frozen, the C11 document locked, the C10 deliverable and
    `report.released`. Raises on any change; then nothing is written."""
    from abacus.modules.assurance.events import ReportReleased
    from abacus.modules.reporting import api as c11

    work_item_id = UUID(request.work_item_id)
    engagement_id = UUID(request.engagement_id)
    released_by = UUID(request.released_by)
    version_id = UUID(request.report_version_id)
    # The row is the EP's own act: the transaction runs as the person (0642's actor CHECK).
    person = TenantContext(UUID(request.tenant_id), "human", str(released_by))
    snap = await snapshot(person, work_item_id)
    if snap.blockers:
        raise GatesNotMet(facts={"gates": ",".join(snap.blockers)})
    if snap.sha256 != request.gate_hash:
        raise ContentChanged(facts={"gate_hash": snap.sha256})
    facts = await engagement_hold_facts(person, engagement_id)
    if facts is None:
        raise NotFound("engagement")
    async with uow(person) as tx:
        await lock_assurance_item(tx, work_item_id)
        if await released(person, work_item_id) is not None:
            raise AlreadyReleased(facts={"work_item_id": str(work_item_id)})
        published = await c11.publish_deliverable(
            tx,
            c11.DeliverableSpec(
                client_id=facts.client_id,
                kind="audit_report",
                title="Independent auditor's report",
                source_module="assurance",
                source_ref=f"report_release:{work_item_id}",
                evidence_version_id=evidence_version_id,
                render_hash=render_hash,
                page_count=page_count,
                audiences=await _audiences(person, engagement_id),  # type: ignore[arg-type]  # DeliverableAudience
                published_by_user_id=released_by,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                generated_document_id=UUID(request.draft_document_id),
            ),
        )
        release_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO report_releases (tenant_id, engagement_id, work_item_id, kind, "
                    "report_version_id, report_version_hash, released_by, report_date, city, "
                    "gate_snapshot, gate_snapshot_sha256, final_document_version_id, "
                    "deliverable_ids, approval_grant_id, idempotency_key, actor_kind, actor_id) "
                    "VALUES (:tenant, :engagement, :wi, 'original', :version, :version_hash, "
                    ":by, :report_date, :city, CAST(:snapshot AS jsonb), :snapshot_sha, :final, "
                    ":deliverables, :grant, :key, 'human', :by) RETURNING id"
                ),
                {
                    "tenant": UUID(request.tenant_id),
                    "engagement": engagement_id,
                    "wi": work_item_id,
                    "version": version_id,
                    "version_hash": snap.report_version_hash,
                    "by": released_by,
                    "report_date": snap.report_date or (await clock.today(person)),
                    "city": snap.city,
                    "snapshot": json.dumps(snap.canonical(), sort_keys=True),
                    "snapshot_sha": snap.sha256,
                    "final": final_version_id,
                    "deliverables": [published.deliverable_id],
                    "grant": UUID(request.grant_id),
                    "key": request.idempotency_key,
                },
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE audit_reports SET status = 'released', version = version + 1, "
                "updated_at = clock_timestamp() "
                "WHERE work_item_id = :wi AND status IN ('draft', 'approved')"
            ),
            {"wi": work_item_id},
        )
        await c11.lock(tx, UUID(request.draft_document_id), f"report_release:{release_id}")
        await advance_by_gate(tx, person, engagement_id, "released", "G8", released_by)
        tx.emit(
            ReportReleased(
                release_id=release_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                report_version_id=version_id,
                final_document_version_id=final_version_id,
            )
        )
        tx.record(
            "report.released",
            target=Target("report_release", release_id),
            after=Ref(
                work_item=work_item_id,
                gate_hash=snap.sha256,
                final=final_version_id,
                deliverable=published.deliverable_id,
            ),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return release_id


async def fail_release(request: ReleaseRequest, reason: str) -> None:
    """A refused or failed release: void the grant if it is still live, audit the reason, and
    record nothing else (AUD-24 c's words come from the reason)."""
    from abacus.modules.identity.api import void_grant

    system = _system(request)
    async with uow(system) as tx:
        await void_grant(tx, UUID(request.grant_id))
        tx.record(
            "report.release_failed",
            target=Target(RELEASE_SUBJECT, UUID(request.report_version_id)),
            after=Ref(reason=reason),
            scope=Scope(
                engagement_id=UUID(request.engagement_id),
                work_item_id=UUID(request.work_item_id),
            ),
        )
