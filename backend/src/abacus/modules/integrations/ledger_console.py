"""CLS-11's ledger console (C-02-T20; TASK-8709; SPEC-700 AC-23, AC-24; ADR-344; DEC-5706). Red.

The console reads one client entity's QuickBooks Online connection on the person's own walls
(`entity_connections`: a walled entity answers 404, INV-3): its health in the console's words
(connected, needs attention, needs reauth from the reauth reasons, disconnected), the client
owner's write grant (who authorised it), the last sync, and the posting tiles, log, activity and
closing date. Posting batches and closing-date events are adjustments' records, read through the
provider adjustments registers (`register_posting_log`; integrations never imports adjustments,
ADR-008). The CSV is deterministic: fixed columns, newest batch first, ids never shown.

A connection needing reauth refuses posting everywhere: the W1 gate reads the same health
(`connection_needs_reauth`).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.safe_xlsx import safe_text
from abacus.modules.identity.api import AuthContext, names_of

REAUTH_REASONS: Final = frozenset({"token_expired", "invalid_grant", "firm_app_disabled"})
LEDGER_LABEL: Final = "QuickBooks Online"
CSV_COLUMNS: Final = (
    "batch_code", "period", "status", "entry_count", "approved_count", "first_external_ref",
    "last_external_ref", "resolved_failures",
)  # fmt: skip


@dataclass(frozen=True)
class LogRow:
    batch_id: UUID
    batch_code: str
    period: str
    status: str
    entry_count: int
    approved_count: int
    first_external_ref: str | None
    last_external_ref: str | None
    resolved_failures: int
    failure_count: int
    posted_at: datetime | None
    posted_by: UUID | None


@dataclass(frozen=True)
class ClosingDate:
    closing_date: date
    set_by: UUID | None
    at: datetime


@dataclass(frozen=True)
class PostingFacts:
    """What adjustments answers about one entity's postings."""

    rows: tuple[LogRow, ...]
    proposed_entries: int
    closing_date: ClosingDate | None


PostingLog = Callable[[TenantContext, UUID], Awaitable[PostingFacts]]
_providers: list[PostingLog] = []


def register_posting_log(provider: PostingLog) -> None:
    _providers[:] = [provider]


async def posting_facts(tenant: TenantContext, client_entity_id: UUID) -> PostingFacts:
    if not _providers:
        return PostingFacts((), 0, None)
    return await _providers[0](tenant, client_entity_id)


BatchEntity = Callable[[TenantContext, UUID], Awaitable[UUID | None]]
_batch_entities: list[BatchEntity] = []


def register_batch_entity(provider: BatchEntity) -> None:
    """C-02-T20 (S51 partials): a posting batch's client entity, from adjustments (which owns
    the batches), so the drawer authorises on the entity before reading."""
    _batch_entities[:] = [provider]


def health_of(status: str, reason: str | None) -> str:
    if status == "revoked":
        return "disconnected"
    if status == "needs_attention":
        return "needs_reauth" if reason in REAUTH_REASONS else "needs_attention"
    return "connected"


_GRANT = text(
    "SELECT event, granted_by_client_user_id, at FROM connection_write_grants "
    "WHERE connection_id = :c AND client_entity_id = :ce AND capability_id = :cap "
    "ORDER BY at DESC, id DESC LIMIT 1"
)


@dataclass(frozen=True)
class Console:
    client_entity_id: UUID
    client_entity_name: str
    tiles: dict[str, object]
    connection: dict[str, object] | None


async def _qbo(ctx: AuthContext, client_entity_id: UUID) -> Any:  # noqa: ANN401 # Any: connections' view
    from abacus.modules.connections.api import entity_connections

    found = await entity_connections(ctx, client_entity_id)
    return next((c for c in found.connections if c.provider == "quickbooks_online"), None)


def _tiles(facts: PostingFacts) -> dict[str, object]:
    posted = sum(r.entry_count for r in facts.rows if r.status == "posted")
    failed = sum(r.failure_count - r.resolved_failures for r in facts.rows)
    return {
        "posted": posted,
        "proposed": facts.proposed_entries,
        "failed_post": max(failed, 0),
        "resolved_failures": sum(r.resolved_failures for r in facts.rows),
        "closing_date": None if facts.closing_date is None else facts.closing_date.closing_date,
    }


async def ledger_console(ctx: AuthContext, client_entity_id: UUID) -> Console:
    from abacus.modules.integrations.writes import W1_CAPABILITY
    from abacus.modules.organisations.api import entity_name

    qbo = await _qbo(ctx, client_entity_id)  # authorises on the entity (walls: 404)
    facts = await posting_facts(ctx.tenant, client_entity_id)
    name = await entity_name(ctx.tenant, client_entity_id) or ""
    if qbo is None:
        return Console(client_entity_id, name, _tiles(facts), None)
    async with tenant_session(ctx.tenant) as session:
        grant = (
            await session.execute(
                _GRANT, {"c": qbo.id, "ce": client_entity_id, "cap": W1_CAPABILITY}
            )
        ).first()
    people = [p for p in (
        grant.granted_by_client_user_id if grant is not None else None,
        facts.closing_date.set_by if facts.closing_date is not None else None,
    ) if p is not None]  # fmt: skip
    names = await names_of(people) if people else {}
    closing = facts.closing_date
    pane: dict[str, object] = {
        "connection_id": qbo.id,
        "health": health_of(qbo.status, qbo.status_reason),
        "authorized_by": names.get(grant.granted_by_client_user_id) if grant is not None else None,
        "write_granted": grant is not None and grant.event == "granted",
        "last_sync_at": qbo.last_sync_at,
        "closing_date": None if closing is None else closing.closing_date,
        "closing_date_set_by": None if closing is None or closing.set_by is None
        else names.get(closing.set_by),
        "closing_date_set_at": None if closing is None else closing.at,
    }  # fmt: skip
    return Console(client_entity_id, name, _tiles(facts), pane)


async def posting_log(
    ctx: AuthContext, client_entity_id: UUID, *, period: str | None, status: str | None
) -> list[LogRow]:
    await _qbo(ctx, client_entity_id)  # the same authorisation and walls as the console
    rows = (await posting_facts(ctx.tenant, client_entity_id)).rows
    return [
        r for r in rows
        if (period is None or r.period == period) and (status is None or r.status == status)
    ]  # fmt: skip


async def posting_batch(ctx: AuthContext, batch_id: UUID) -> LogRow:
    """CLS-11 b2: one batch's log row; the same authorisation and walls as the console (an
    unknown or walled batch answers 404, never a hint it exists)."""
    entity = await _batch_entities[0](ctx.tenant, batch_id) if _batch_entities else None
    if entity is None:
        raise NotFound("posting_batch")
    rows = await posting_log(ctx, entity, period=None, status=None)
    found = next((r for r in rows if r.batch_id == batch_id), None)
    if found is None:
        raise NotFound("posting_batch")
    return found


def posting_log_csv(rows: Sequence[LogRow]) -> bytes:
    """Deterministic: fixed columns, the log's order, `\\n` line ends, no ids."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        writer.writerow([_cell(cast(object, getattr(r, c))) for c in CSV_COLUMNS])
    return out.getvalue().encode()


def _cell(value: object) -> object:
    """A provider's reference is client-system text (ADR-052): never a spreadsheet formula."""
    if value is None:
        return ""
    return safe_text(value) if isinstance(value, str) else value


@dataclass(frozen=True)
class LedgerEvent:
    at: datetime
    kind: str
    batch_code: str | None = None
    count: int | None = None
    actor: UUID | None = None


async def ledger_activity(
    ctx: AuthContext, client_entity_id: UUID, *, kind: str | None
) -> list[tuple[LedgerEvent, str | None]]:
    """Posts, failures, closing dates and the last sync, newest first, each with its actor's
    name resolved at read time."""
    qbo = await _qbo(ctx, client_entity_id)
    facts = await posting_facts(ctx.tenant, client_entity_id)
    events: list[LedgerEvent] = []
    for r in facts.rows:
        if r.posted_at is not None:
            events.append(
                LedgerEvent(r.posted_at, "post", r.batch_code, r.entry_count, r.posted_by)
            )
        if r.failure_count > r.resolved_failures and r.posted_at is not None:
            open_failures = r.failure_count - r.resolved_failures
            events.append(
                LedgerEvent(r.posted_at, "sync_failed", r.batch_code, open_failures, r.posted_by)
            )
    if facts.closing_date is not None:
        events.append(LedgerEvent(facts.closing_date.at, "closing_date", None, None,
                               facts.closing_date.set_by))  # fmt: skip
    if qbo is not None and qbo.last_sync_at is not None:
        events.append(LedgerEvent(qbo.last_sync_at, "sync"))
    if kind is not None:
        events = [e for e in events if e.kind == kind]
    events.sort(key=lambda e: e.at, reverse=True)
    names = await names_of([e.actor for e in events if e.actor is not None])
    return [(e, names.get(e.actor) if e.actor is not None else None) for e in events]


__all__ = [
    "LEDGER_LABEL",
    "ClosingDate",
    "Console",
    "LedgerEvent",
    "LogRow",
    "PostingFacts",
    "health_of",
    "ledger_activity",
    "ledger_console",
    "posting_batch",
    "posting_facts",
    "posting_log",
    "posting_log_csv",
    "register_batch_entity",
    "register_posting_log",
]
