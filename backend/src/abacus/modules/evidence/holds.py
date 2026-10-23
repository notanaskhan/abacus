"""Legal holds (Q-02-T29; Q-02 AC-34 to AC-37; ADR-033; DEC-71 / P-14; DEC-228). PROTECTED.

A person places a hold on a client, a client and tax year, an engagement or a work item. The
database is the truth: in the placing transaction every evidence version in scope gets a
`hold_objects` row, and every version created later in a held scope gets one in its own creating
transaction (`inherit_holds`), so the hold check counts it before any processing. S3 follows:
`LegalHoldApply` sets the object legal hold per stored version, the `evidence_version.created`
consumer does the same for a new version, and `LegalHoldRelease` lifts it only where no other
open hold names the same stored object (content-addressed: two versions may share one object).

    held = await holds_covering(tenant, version_ids)   # registered as the kernel's hold check

`holds_covering` reads both the rows and, for open holds, the scope itself, so a version created
while a hold was being placed is still held before the workflow catches up. Lifting is allowed
only once a hold is active. Placing and lifting are human-only (the matrix denies agent and
system, the table binds the person, the audit guard refuses `legal_hold.placed`/`.lifted`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import ScalarSelect, Uuid, column, func, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import COMPLIANCE_LEGAL_HOLDS
from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.holds import register_hold_check
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import (
    engagement_hold_facts,
    engagements_in_hold_scope,
    get_ref,
    work_item_engagement,
)
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import LegalHoldLifted, LegalHoldPlaced
from abacus.modules.evidence.storage import StoredObject
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    member_facts,
    resolve_scope,
    visible_clients,
)

ScopeKind = Literal["client", "client_tax_year", "engagement", "work_item"]
ReasonCode = Literal["irs_examination", "litigation", "regulatory_inquiry", "subpoena", "other"]
HoldStatus = Literal["applying", "active", "releasing", "released"]
OPEN: Final = ("applying", "active")  # holds that cover new versions
BATCH: Final = 200  # stored versions per activity call
_NOTIFY_ENGAGEMENTS: Final = 200  # engagement ids carried on the placed event, at most
_log = get_logger(__name__)


class HoldNotActive(DomainConflict):
    """Only an active hold can be lifted: wait until it finishes applying, or it is already
    lifted."""

    code = "hold_not_active"


class NotifyNotMember(DomainInvalid):
    """Everyone on the notify list must be a current member of the firm's staff."""

    code = "notify_not_member"


@dataclass(frozen=True)
class HoldScope:
    kind: ScopeKind
    client_id: UUID | None = None
    tax_year: int | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None


@dataclass(frozen=True)
class ResolvedScope:
    kind: ScopeKind
    client_id: UUID
    tax_year: int | None
    engagement_id: UUID | None
    work_item_id: UUID | None


@dataclass(frozen=True)
class HoldView:
    id: UUID
    scope_kind: ScopeKind
    client_id: UUID
    tax_year: int | None
    engagement_id: UUID | None
    work_item_id: UUID | None
    reason_code: ReasonCode
    status: HoldStatus
    placed_by: UUID
    placed_at: datetime
    released_by: UUID | None
    released_at: datetime | None
    objects_held: int  # versions this hold still counts
    objects_applied: int  # of those, the ones whose S3 hold is confirmed


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "legal_holds")


async def _require_flag(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, COMPLIANCE_LEGAL_HOLDS):
        raise NotFound(COMPLIANCE_LEGAL_HOLDS.name)


# --- scope ------------------------------------------------------------------------------------


async def _resolve(ctx: AuthContext, scope: HoldScope) -> ResolvedScope:
    """The scope with its client; `NotFound` for anything outside the tenant or malformed."""
    if scope.kind in ("client", "client_tax_year"):
        if scope.client_id is None or (scope.kind == "client_tax_year") != (
            scope.tax_year is not None
        ):
            raise NotFound("legal_hold_scope")
        if await resolve_scope(ctx.tenant, "client", scope.client_id) is None:
            raise NotFound("legal_hold_scope")
        return ResolvedScope(scope.kind, scope.client_id, scope.tax_year, None, None)
    if scope.kind == "engagement":
        if scope.engagement_id is None:
            raise NotFound("legal_hold_scope")
        ref = await get_ref(ctx, scope.engagement_id)
        return ResolvedScope("engagement", ref.client_id, None, ref.id, None)
    if scope.work_item_id is None:
        raise NotFound("legal_hold_scope")
    engagement_id = await work_item_engagement(ctx.tenant, scope.work_item_id)
    if engagement_id is None:
        raise NotFound("legal_hold_scope")
    ref = await get_ref(ctx, engagement_id)
    return ResolvedScope("work_item", ref.client_id, None, engagement_id, scope.work_item_id)


async def _engagements_of(tenant: TenantContext, scope: ResolvedScope) -> list[UUID]:
    """The engagements whose versions the scope covers. A work item covers its engagement:
    evidence versions don't name a work item yet (DEC-228)."""
    if scope.engagement_id is not None:
        return [scope.engagement_id]
    return await engagements_in_hold_scope(tenant, scope.client_id, scope.tax_year)


_ROW = text(
    "SELECT id, scope_kind, client_id, tax_year, engagement_id, work_item_id, status "
    "FROM legal_holds WHERE id = :id"
)


async def _hold_scope(session: AsyncSession, hold_id: UUID) -> tuple[ResolvedScope, str] | None:
    row = (await session.execute(_ROW, {"id": hold_id})).mappings().one_or_none()
    if row is None:
        return None
    return (
        ResolvedScope(
            cast(ScopeKind, row["scope_kind"]),
            row["client_id"],
            row["tax_year"],
            row["engagement_id"],
            row["work_item_id"],
        ),
        str(row["status"]),
    )


_ADD_OBJECTS = text(
    "INSERT INTO hold_objects (tenant_id, hold_id, evidence_version_id, object_key, "
    "object_version_id) SELECT v.tenant_id, :hold, v.id, v.storage_key, v.storage_version_id "
    "FROM evidence_versions v WHERE v.engagement_id = ANY(:engagements) "
    "ON CONFLICT (hold_id, evidence_version_id) DO NOTHING"
)


_MISSING = text(
    "SELECT count(*) FROM evidence_versions v WHERE v.engagement_id = ANY(:engagements) "
    "AND NOT EXISTS (SELECT 1 FROM hold_objects o WHERE o.hold_id = :hold "
    "AND o.evidence_version_id = v.id)"
)


async def _add_objects(session: AsyncSession, hold_id: UUID, engagements: Sequence[UUID]) -> int:
    if not engagements:
        return 0
    result = await session.execute(
        _ADD_OBJECTS, {"hold": hold_id, "engagements": list(engagements)}
    )
    return int(getattr(result, "rowcount", 0) or 0)


# --- placing and lifting (people only) ---------------------------------------------------------


async def place_hold(
    ctx: AuthContext,
    scope: HoldScope,
    reason_code: ReasonCode,
    details: str | None,
    notify_user_ids: Sequence[UUID],
) -> HoldView:
    """A partner, security admin or firm admin, with fresh MFA, holds a scope: every version in it
    is counted at once and `LegalHoldApply` sets the S3 holds (started from the outbox)."""
    await _require_flag(ctx)
    resolved = await _resolve(ctx, scope)
    await authorise(ctx, "legal_hold.place", Resource.client(ctx.tenant_id, resolved.client_id))
    notify = sorted(set(notify_user_ids))
    for user in notify:
        member = await member_facts(ctx.tenant, user)
        if member is None or member.client:
            raise NotifyNotMember
    engagements = await _engagements_of(ctx.tenant, resolved)
    hold_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO legal_holds (id, tenant_id, scope_kind, client_id, tax_year, "
                "engagement_id, work_item_id, reason_code, details, notify_user_ids, placed_by) "
                "VALUES (:id, :tenant, :kind, :client, :year, :engagement, :work_item, :reason, "
                ":details, CAST(:notify AS uuid[]), :by)"
            ),
            {
                "id": hold_id,
                "tenant": ctx.tenant_id,
                "kind": resolved.kind,
                "client": resolved.client_id,
                "year": resolved.tax_year,
                "engagement": resolved.engagement_id,
                "work_item": resolved.work_item_id,
                "reason": reason_code,
                "details": details,
                "notify": [str(u) for u in notify],
                "by": ctx.user_id,
            },
        )
        counted = await _add_objects(tx.session, hold_id, engagements)
        tx.record(
            "legal_hold.placed",
            target=Target("legal_hold", hold_id),
            after=Ref(client_id=resolved.client_id, objects=counted),
        )
        tx.emit(
            LegalHoldPlaced(
                hold_id=hold_id,
                client_id=resolved.client_id,
                engagement_id=resolved.engagement_id,
                work_item_id=resolved.work_item_id,
                engagement_ids=tuple(engagements[:_NOTIFY_ENGAGEMENTS]),
                notify_user_ids=tuple(notify),
                by_user=ctx.user_id,
            )
        )
    return await _view(ctx.tenant, hold_id)


async def lift_hold(ctx: AuthContext, hold_id: UUID, reason: str) -> HoldView:
    """Lift an active hold, with fresh MFA. Objects stay held while another hold covers them;
    `LegalHoldRelease` clears S3 holds where none does (AC-35)."""
    await _require_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = await _hold_scope(session, hold_id)
    if found is None:
        raise NotFound("legal_hold")
    scope, _status = found
    await authorise(ctx, "legal_hold.lift", Resource.client(ctx.tenant_id, scope.client_id))
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.execute(
            text(
                "UPDATE legal_holds SET status = 'releasing', released_by = :by, "
                "release_reason = :reason WHERE id = :id AND status = 'active'"
            ),
            {"id": hold_id, "by": ctx.user_id, "reason": reason},
        )
        if not getattr(moved, "rowcount", 0):
            raise HoldNotActive
        tx.record("legal_hold.lifted", target=Target("legal_hold", hold_id))
        tx.emit(LegalHoldLifted(hold_id=hold_id, client_id=scope.client_id, by_user=ctx.user_id))
    return await _view(ctx.tenant, hold_id)


# --- reading ----------------------------------------------------------------------------------

_holds = table(
    "legal_holds",
    column("id", Uuid),
    column("scope_kind"),
    column("client_id", Uuid),
    column("tax_year"),
    column("engagement_id", Uuid),
    column("work_item_id", Uuid),
    column("reason_code"),
    column("status"),
    column("placed_by", Uuid),
    column("placed_at"),
    column("released_by", Uuid),
    column("released_at"),
)
_objects = table(
    "hold_objects",
    column("hold_id", Uuid),
    column("applied_at"),
    column("released_at"),
)


def _counts() -> tuple[ScalarSelect[int], ScalarSelect[int]]:
    held = (
        select(func.count())
        .select_from(_objects)
        .where(_objects.c.hold_id == _holds.c.id, _objects.c.released_at.is_(None))
        .scalar_subquery()
    )
    applied = (
        select(func.count())
        .select_from(_objects)
        .where(
            _objects.c.hold_id == _holds.c.id,
            _objects.c.released_at.is_(None),
            _objects.c.applied_at.is_not(None),
        )
        .scalar_subquery()
    )
    return held, applied


def _to_view(row: dict[str, object]) -> HoldView:
    return HoldView(
        id=cast(UUID, row["id"]),
        scope_kind=cast(ScopeKind, row["scope_kind"]),
        client_id=cast(UUID, row["client_id"]),
        tax_year=cast(int | None, row["tax_year"]),
        engagement_id=cast(UUID | None, row["engagement_id"]),
        work_item_id=cast(UUID | None, row["work_item_id"]),
        reason_code=cast(ReasonCode, row["reason_code"]),
        status=cast(HoldStatus, row["status"]),
        placed_by=cast(UUID, row["placed_by"]),
        placed_at=cast(datetime, row["placed_at"]),
        released_by=cast(UUID | None, row["released_by"]),
        released_at=cast(datetime | None, row["released_at"]),
        objects_held=int(cast(int, row["objects_held"])),
        objects_applied=int(cast(int, row["objects_applied"])),
    )


async def _view(tenant: TenantContext, hold_id: UUID) -> HoldView:
    held, applied = _counts()
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    select(
                        _holds, held.label("objects_held"), applied.label("objects_applied")
                    ).where(_holds.c.id == hold_id)
                )
            )
            .mappings()
            .one()
        )
    return _to_view(dict(row))


async def list_holds(ctx: AuthContext) -> list[HoldView]:
    """Holds on clients the caller may read (walled clients absent, no hidden count), newest
    first, with their counts. Never the details text or the release reason."""
    await _require_flag(ctx)
    seen = await visible_clients(ctx, "legal_hold.read", _holds.c.client_id)
    held, applied = _counts()
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    select(_holds, held.label("objects_held"), applied.label("objects_applied"))
                    .where(seen)
                    .order_by(_holds.c.placed_at.desc(), _holds.c.id)
                )
            )
            .mappings()
            .all()
        )
    return [_to_view(dict(r)) for r in rows]


# --- the hold check (registered into kernel.holds) ---------------------------------------------

_HELD_ROWS = text(
    "SELECT DISTINCT evidence_version_id FROM hold_objects "
    "WHERE released_at IS NULL AND evidence_version_id = ANY(:ids)"
)
_VERSION_ENGAGEMENTS = text("SELECT id, engagement_id FROM evidence_versions WHERE id = ANY(:ids)")
_OPEN_HOLDS = text(
    "SELECT scope_kind, client_id, tax_year, engagement_id FROM legal_holds "
    "WHERE status IN ('applying', 'active')"
)


def _covers(
    hold: dict[str, object], engagement_id: UUID, client_id: UUID, years: frozenset[int]
) -> bool:
    kind = hold["scope_kind"]
    if kind in ("engagement", "work_item"):
        return hold["engagement_id"] == engagement_id
    if hold["client_id"] != client_id:
        return False
    return kind == "client" or hold["tax_year"] in years


async def holds_covering(tenant: TenantContext, version_ids: Sequence[UUID]) -> frozenset[UUID]:
    """The versions among `version_ids` that any hold covers: an unreleased hold object, or an
    open hold whose scope contains the version (a version created while the hold was placed).
    A version this firm doesn't have is reported held: the caller can't erase what it can't see."""
    ids = list(dict.fromkeys(version_ids))
    if not ids:
        return frozenset()
    system = _system(tenant.tenant_id)
    async with tenant_session(system) as session:
        held = set((await session.scalars(_HELD_ROWS, {"ids": ids})).all())
        engagement_of = {
            row.id: row.engagement_id
            for row in (await session.execute(_VERSION_ENGAGEMENTS, {"ids": ids})).all()
        }
        open_holds = [dict(r) for r in (await session.execute(_OPEN_HOLDS)).mappings().all()]
    held |= {v for v in ids if v not in engagement_of}
    if open_holds:
        facts = {e: await engagement_hold_facts(system, e) for e in set(engagement_of.values())}
        for version, engagement in engagement_of.items():
            known = facts.get(engagement)
            if known is None or any(
                _covers(h, engagement, known.client_id, known.years) for h in open_holds
            ):
                held.add(version)
    return frozenset(held)


register_hold_check(holds_covering)


# --- inheritance (in the version's own transaction) -------------------------------------------


async def inherit_holds(tx: UnitOfWork, version_id: UUID, engagement_id: UUID) -> int:
    """Count a new version under every open hold covering its engagement, inside the creating
    unit of work (AC-36): it is held before its `evidence_version.created` processing starts.
    The S3 hold follows from the outbox (`apply_version_holds`)."""
    session = tx.session
    if (
        await session.scalar(
            text("SELECT 1 FROM legal_holds WHERE status IN ('applying', 'active') LIMIT 1")
        )
        is None
    ):
        return 0
    tenant = (await transaction_context(session)).tenant_id
    facts = await engagement_hold_facts(_system(tenant), engagement_id)
    if facts is None:
        return 0
    open_holds = (
        (
            await session.execute(
                text(
                    "SELECT id, scope_kind, client_id, tax_year, engagement_id FROM legal_holds "
                    "WHERE status IN ('applying', 'active')"
                )
            )
        )
        .mappings()
        .all()
    )
    covering = [
        h["id"]
        for h in open_holds
        if _covers(dict(h), engagement_id, facts.client_id, facts.years)
    ]
    for hold_id in covering:
        await session.execute(
            text(
                "INSERT INTO hold_objects (tenant_id, hold_id, evidence_version_id, object_key, "
                "object_version_id) SELECT v.tenant_id, :hold, v.id, v.storage_key, "
                "v.storage_version_id FROM evidence_versions v WHERE v.id = :version "
                "ON CONFLICT (hold_id, evidence_version_id) DO NOTHING"
            ),
            {"hold": hold_id, "version": version_id},
        )
    if covering:
        tx.record(
            "legal_hold.inherited",
            target=Target("evidence_version", version_id),
            after=Ref(holds=len(covering)),
        )
    return len(covering)


# --- S3 (activities and the outbox consumer; never inside a transaction) -----------------------


async def _open_on(session: AsyncSession, key: str, version: str) -> int:
    return int(
        await session.scalar(
            text(
                "SELECT count(*) FROM hold_objects WHERE released_at IS NULL "
                "AND object_key = :key AND object_version_id = :version"
            ),
            {"key": key, "version": version},
        )
        or 0
    )


def _stored(key: str, version: str) -> StoredObject:
    return StoredObject(key, version, "", 0)


async def _settle(tenant: TenantContext, objects: Sequence[tuple[str, str]]) -> None:
    """After a release: an object no unreleased hold object names is let go; one a hold reached in
    the meantime is held again. Set last wins either way (see DEC-228)."""
    for key, version in dict.fromkeys(objects):
        async with tenant_session(tenant) as session:
            still = await _open_on(session, key, version)
        await storage.set_legal_hold(_stored(key, version), on=still > 0)


async def _apply_pending(
    tenant_id: UUID, *, hold_id: UUID | None = None, version_id: UUID | None = None
) -> int:
    """Set the S3 hold on pending rows of a hold or of a version, then stamp them. One audit
    event."""
    system = _system(tenant_id)
    async with tenant_session(system) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT hold_id, evidence_version_id, object_key, object_version_id "
                    "FROM hold_objects WHERE applied_at IS NULL AND released_at IS NULL "
                    "AND (CAST(:hold AS uuid) IS NULL OR hold_id = :hold) "
                    "AND (CAST(:version AS uuid) IS NULL OR evidence_version_id = :version) "
                    "ORDER BY evidence_version_id LIMIT :batch"
                ),
                {"hold": hold_id, "version": version_id, "batch": BATCH},
            )
        ).all()
    if not rows:
        return 0
    for key, version in dict.fromkeys((r.object_key, r.object_version_id) for r in rows):
        await storage.set_legal_hold(_stored(key, version), on=True)
    async with uow(system) as tx:
        stamped = await tx.session.execute(
            text(
                "UPDATE hold_objects SET applied_at = clock_timestamp() "
                "WHERE hold_id = ANY(:holds) AND evidence_version_id = ANY(:versions) "
                "AND applied_at IS NULL AND released_at IS NULL"
            ),
            {
                "holds": list({r.hold_id for r in rows}),
                "versions": list({r.evidence_version_id for r in rows}),
            },
        )
        count = int(getattr(stamped, "rowcount", 0) or 0)
        tx.record(
            "legal_hold.applied",
            target=Target("firm", tenant_id),
            after=Ref(objects=count),
        )
    if count < len(rows):  # some were released meanwhile: don't leave a stray S3 hold
        await _settle(system, [(r.object_key, r.object_version_id) for r in rows])
    return count


async def apply_batch(tenant_id: UUID, hold_id: UUID) -> int:
    """`LegalHoldApply`'s step: count any version in scope not yet counted, set the S3 hold on up
    to `BATCH` pending ones; how many stay pending. 0 when the hold isn't applying or active."""
    system = _system(tenant_id)
    async with tenant_session(system) as session:
        found = await _hold_scope(session, hold_id)
    if found is None:
        raise NotFound("legal_hold")
    scope, status = found
    if status not in OPEN:
        return 0
    engagements = await _engagements_of(system, scope)
    if engagements:
        async with tenant_session(system) as session:
            missing = int(
                await session.scalar(_MISSING, {"hold": hold_id, "engagements": engagements}) or 0
            )
        if missing:  # a version created while the hold was placed (DEC-228)
            async with uow(system) as tx:
                added = await _add_objects(tx.session, hold_id, engagements)
                tx.record(
                    "legal_hold.counted",
                    target=Target("legal_hold", hold_id),
                    after=Ref(objects=added),
                )
    await _apply_pending(tenant_id, hold_id=hold_id)
    async with tenant_session(system) as session:
        return int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM hold_objects WHERE hold_id = :hold "
                    "AND applied_at IS NULL AND released_at IS NULL"
                ),
                {"hold": hold_id},
            )
            or 0
        )


async def activate(tenant_id: UUID, hold_id: UUID) -> str:
    """Every version in scope is held in S3: the hold is active. Repeat-safe; the hold's status."""
    return await _advance(tenant_id, hold_id, "applying", "active", "legal_hold.activated")


async def _advance(tenant_id: UUID, hold_id: UUID, start: str, end: str, action: str) -> str:
    """Move the hold from `start` to `end` (the system's step, audited); otherwise leave it."""
    system = _system(tenant_id)
    async with tenant_session(system) as session:
        status = await session.scalar(
            text("SELECT status FROM legal_holds WHERE id = :id"), {"id": hold_id}
        )
    if status is None:
        raise NotFound("legal_hold")
    if status != start:
        return str(status)
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE legal_holds SET status = :end, applied_at = CASE WHEN :end = 'active' "
                "THEN clock_timestamp() ELSE applied_at END, released_at = CASE WHEN "
                ":end = 'released' THEN clock_timestamp() ELSE released_at END "
                "WHERE id = :id AND status = :start"
            ),
            {"id": hold_id, "start": start, "end": end},
        )
        tx.record(action, target=Target("legal_hold", hold_id))
    return end


async def release_batch(tenant_id: UUID, hold_id: UUID) -> int:
    """`LegalHoldRelease`'s step: for up to `BATCH` of the hold's unreleased objects, clear the S3
    hold where no other hold names the object, then stamp them released, then re-check (a hold
    placed meanwhile wins). How many stay unreleased."""
    system = _system(tenant_id)
    async with tenant_session(system) as session:
        status = await session.scalar(
            text("SELECT status FROM legal_holds WHERE id = :id"), {"id": hold_id}
        )
        if status is None:
            raise NotFound("legal_hold")
        if status != "releasing":
            return 0
        rows = (
            await session.execute(
                text(
                    "SELECT evidence_version_id, object_key, object_version_id FROM hold_objects "
                    "WHERE hold_id = :hold AND released_at IS NULL "
                    "ORDER BY evidence_version_id LIMIT :batch"
                ),
                {"hold": hold_id, "batch": BATCH},
            )
        ).all()
        objects = list(dict.fromkeys((r.object_key, r.object_version_id) for r in rows))
        others: dict[tuple[str, str], int] = {}
        for key, version in objects:
            others[(key, version)] = int(
                await session.scalar(
                    text(
                        "SELECT count(*) FROM hold_objects WHERE released_at IS NULL "
                        "AND object_key = :key AND object_version_id = :version "
                        "AND hold_id <> :hold"
                    ),
                    {"key": key, "version": version, "hold": hold_id},
                )
                or 0
            )
    if not rows:
        return 0
    free = [o for o in objects if others[o] == 0]
    for key, version in free:
        await storage.set_legal_hold(_stored(key, version), on=False)
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE hold_objects SET released_at = clock_timestamp() "
                "WHERE hold_id = :hold AND evidence_version_id = ANY(:versions) "
                "AND released_at IS NULL"
            ),
            {"hold": hold_id, "versions": [r.evidence_version_id for r in rows]},
        )
        tx.record(
            "legal_hold.released",
            target=Target("legal_hold", hold_id),
            after=Ref(objects=len(rows), cleared=len(free)),
        )
    # A hold that reached a cleared object meanwhile holds it again.
    async with tenant_session(system) as session:
        regained = [o for o in free if await _open_on(session, *o) > 0]
    for key, version in regained:
        await storage.set_legal_hold(_stored(key, version), on=True)
    async with tenant_session(system) as session:
        return int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM hold_objects WHERE hold_id = :hold "
                    "AND released_at IS NULL"
                ),
                {"hold": hold_id},
            )
            or 0
        )


async def finish_release(tenant_id: UUID, hold_id: UUID) -> str:
    """Every object is let go: the hold is released. Repeat-safe; the hold's status."""
    return await _advance(tenant_id, hold_id, "releasing", "released", "legal_hold.ended")


async def apply_version_holds(tenant_id: UUID, version_id: UUID) -> int:
    """The `evidence_version.created` consumer (HoldInherit): set the S3 hold for a new version
    that `inherit_holds` counted. Repeat-safe; how many hold objects were stamped."""
    return await _apply_pending(tenant_id, version_id=version_id)


__all__ = [
    "BATCH",
    "HoldNotActive",
    "HoldScope",
    "HoldView",
    "NotifyNotMember",
    "ReasonCode",
    "ScopeKind",
    "activate",
    "apply_batch",
    "apply_version_holds",
    "finish_release",
    "holds_covering",
    "inherit_holds",
    "lift_hold",
    "list_holds",
    "place_hold",
    "release_batch",
]
