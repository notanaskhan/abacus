"""Destruction assembly and its reads (Q-05-T11; TASK-8713; SPEC-711 AC-21 to AC-23; DEC-5709).
Red. Dark behind `records.destruction`.

- **Assemble** (`assemble`, DestructionAssembleWorkflow's activity, quarterly per tenant on the
  platform schedule): the tenant's live evidence versions with their facts (record type
  `client_document`, the engagement's service line and period end as the policy anchor, an active
  legal hold on the client, an unlocked archive through the reader assurance registers), through
  `eligibility.select`; one `destruction_batches` row per quarter (a second run finds it and writes
  nothing) with its insert-only items, and `destruction_batch.assembled` to the firm's admins.
- **Reads**: the retention summary (tiles), the batch list and detail, and `documents.csv` (an
  audited export; fresh MFA through the matrix).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, datetime, time
from typing import Any, ClassVar, Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.evidence.eligibility import VersionFacts, quarter_ref, select
from abacus.modules.evidence.retention import retain_until_for

RECORD_TYPE: Final = "client_document"
SERVICE_LINES: Final = {
    "audit": "audit", "review": "audit", "compilation": "audit", "ebp_audit": "audit",
    "tax": "tax", "cas_monthly_close": "cas", "advisory": "advisory",
}  # fmt: skip
CT: Final = ZoneInfo("America/Chicago")


class DestructionBatchAssembled(DomainEvent):
    """A quarter's batch is ready for two approvals (notification kind destruction_batch_assembled
    to the firm admins and security admins)."""

    event_type: ClassVar[str] = "destruction_batch.assembled"

    destruction_batch_id: UUID
    ref: str
    eligible_count: int


ArchiveReader = Callable[[TenantContext, Sequence[UUID]], Awaitable[frozenset[UUID]]]
_archives: list[ArchiveReader] = []


def register_unlocked_archives(reader: ArchiveReader) -> None:
    """The engagements whose archive is open but not yet locked (assurance registers it)."""
    _archives[:] = [reader]


Observe = Callable[[str, str], Awaitable[datetime | None]]

_CANDIDATES = text(
    "SELECT v.id, v.storage_key, v.storage_version_id, v.engagement_id "
    "FROM evidence_versions v WHERE v.destroyed_at IS NULL"
)
_HELD_CLIENTS = text(
    "SELECT DISTINCT client_id FROM legal_holds WHERE status IN ('applying', 'active')"
)


async def candidates(tenant: TenantContext, observe: Observe) -> list[VersionFacts]:
    from abacus.modules.engagements.api import engagement_retention_facts

    async with tenant_session(tenant) as session:
        rows = list((await session.execute(_CANDIDATES)).all())
        held_clients = {cast(UUID, c) for c in await session.scalars(_HELD_CLIENTS)}
    facts = await engagement_retention_facts(tenant, sorted({r.engagement_id for r in rows}))
    unlocked: frozenset[UUID] = frozenset()
    if _archives:
        unlocked = await _archives[0](tenant, sorted({r.engagement_id for r in rows}))
    policies: dict[tuple[str, date | None], datetime | None] = {}
    out: list[VersionFacts] = []
    for r in rows:
        e = facts.get(r.engagement_id)
        if e is None:
            continue
        line = SERVICE_LINES.get(e.type, "any")
        anchor = e.period_end
        if (line, anchor) not in policies:
            policies[(line, anchor)] = (
                None if anchor is None else await retain_until_for(
                    tenant, RECORD_TYPE, line, datetime.combine(anchor, time(), CT))
            )  # fmt: skip
        observed = await observe(str(r.storage_key), str(r.storage_version_id))
        out.append(
            VersionFacts(
                r.id, str(r.storage_key), str(r.storage_version_id), RECORD_TYPE, e.client_id,
                policies[(line, anchor)], observed, e.client_id in held_clients,
                r.engagement_id in unlocked,
            )
        )  # fmt: skip
    return out


_BATCH_BY_REF = text("SELECT id FROM destruction_batches WHERE ref = :ref")
_NEW_BATCH = text(
    "INSERT INTO destruction_batches (tenant_id, ref, scope_description, eligible_count, "
    "client_count, confirmation_phrase) VALUES (:t, :ref, :scope, :n, :clients, :phrase) "
    "RETURNING id"
)
_HELD = text("UPDATE destruction_batches SET held_excluded_count = :h WHERE id = :b")
_ITEM = text(
    "INSERT INTO destruction_batch_items (tenant_id, batch_id, evidence_version_id, object_key, "
    "object_version_id, record_type, client_id, eligible_at, retain_until_observed) VALUES "
    "(:t, :b, :v, :key, :ver, :type, :client, :at, :observed)"
)


async def assemble(tenant_id: UUID, now: datetime, observe: Observe) -> UUID | None:
    """The quarter's batch, once; None when nothing is eligible."""
    from abacus.modules.evidence.eligibility import eligible_at

    tenant = TenantContext(tenant_id, "system", "destruction:assemble")
    ref = quarter_ref(now)
    async with tenant_session(tenant) as session:
        found = await session.scalar(_BATCH_BY_REF, {"ref": ref})
    if found is not None:
        return cast(UUID, found)
    chosen = select(await candidates(tenant, observe), now)
    if not chosen.items:
        return None
    scope = f"Former-client records past retention · {ref}"
    async with uow(tenant) as tx:
        batch = cast(
            UUID,
            await tx.session.scalar(
                _NEW_BATCH,
                {"t": tenant_id, "ref": ref, "scope": scope, "n": len(chosen.items),
                 "clients": chosen.clients, "phrase": f"DESTROY {ref}"},
            ),
        )  # fmt: skip
        if chosen.held:
            await tx.session.execute(_HELD, {"h": chosen.held, "b": batch})
        for f in chosen.items:
            await tx.session.execute(
                _ITEM,
                {"t": tenant_id, "b": batch, "v": f.version_id, "key": f.object_key,
                 "ver": f.object_version_id, "type": f.record_type, "client": f.client_id,
                 "at": eligible_at(f), "observed": f.observed_until},
            )  # fmt: skip
        tx.record(
            "destruction_batch.assembled",
            target=Target("destruction_batch", batch),
            after=Ref(items=len(chosen.items), shared_excluded=chosen.shared_excluded),
        )
        tx.emit(
            DestructionBatchAssembled(
                destruction_batch_id=batch, ref=ref, eligible_count=len(chosen.items)
            )
        )
    return batch


# --- reads ---------------------------------------------------------------------------------------

_SUMMARY = text(
    "SELECT count(*) FILTER (WHERE status IN ('awaiting_approval', 'approved')) "
    "AS pending_batches, coalesce(sum(eligible_count - destroyed_count - held_excluded_count) "
    "FILTER (WHERE status IN ('awaiting_approval', 'approved')), 0) AS pending_documents, "
    "(SELECT count(*) FROM legal_holds WHERE status IN ('applying', 'active')) AS active_holds, "
    "(SELECT count(*) FROM retention_policies) AS policies FROM destruction_batches"
)
_BATCHES = text(
    "SELECT id, ref, scope_description, status, assembled_at, eligible_count, "
    "held_excluded_count, destroyed_count, client_count, confirmation_phrase, hold_recheck_at, "
    "version FROM destruction_batches WHERE (CAST(:s AS text) IS NULL OR status = :s) "
    "ORDER BY assembled_at DESC LIMIT 50"
)
_ONE = text(
    "SELECT id, ref, scope_description, status, assembled_at, eligible_count, "
    "held_excluded_count, destroyed_count, client_count, confirmation_phrase, hold_recheck_at, "
    "version FROM destruction_batches WHERE id = :b"
)
_ITEMS = text(
    "SELECT i.evidence_version_id, i.record_type, i.client_id, i.eligible_at, x.reason "
    "FROM destruction_batch_items i LEFT JOIN destruction_item_exclusions x ON x.item_id = i.id "
    "WHERE i.batch_id = :b ORDER BY i.client_id, i.eligible_at, i.evidence_version_id"
)


async def summary(tenant: TenantContext) -> dict[str, int]:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_SUMMARY)).mappings().one()
    return {k: int(cast(int, v)) for k, v in row.items()}


async def batches(tenant: TenantContext, status: str | None) -> list[dict[str, Any]]:  # Any: rows
    async with tenant_session(tenant) as session:
        return [dict(r) for r in (await session.execute(_BATCHES, {"s": status})).mappings()]


async def batch(tenant: TenantContext, batch_id: UUID) -> dict[str, Any]:  # Any: a SQL row
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ONE, {"b": batch_id})).mappings().first()
    if row is None:
        raise NotFound("destruction_batch")
    return dict(row)


async def documents_csv(tenant: TenantContext, batch_id: UUID) -> bytes:
    """The batch's documents, deterministic: one row per item (version id, record type, client,
    eligible from, exclusion), audited by the caller's export."""
    await batch(tenant, batch_id)
    async with tenant_session(tenant) as session:
        rows = list((await session.execute(_ITEMS, {"b": batch_id})).all())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["evidence_version_id", "record_type", "client_id", "eligible_at", "excluded"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2] or "", r[3].isoformat(), r[4] or ""])
    return out.getvalue().encode()


__all__ = [
    "DestructionBatchAssembled",
    "assemble",
    "batch",
    "batches",
    "candidates",
    "documents_csv",
    "register_unlocked_archives",
    "summary",
]
