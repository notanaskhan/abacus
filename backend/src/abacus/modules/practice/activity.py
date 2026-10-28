"""HOME-01's client activity: the `home_activity_items` projection (I-01-T12; I-01 F4 AC4.3, AC4.4;
`home-and-gates.md` §3; DEC-900).

- **Allowlist** (`SOURCES`): the outbox events that become a row, each mapped to an activity code
  (`ACTIVITY_TYPES`, the table's CHECK): a client upload (`evidence.uploaded`), a follow-up sent
  (`follow_up.sent`), a letter recorded (`gate.met` for G3, the interim recorded letter) and an
  agent pre-screen (`upload_review.recorded`). Inbound mail and envelopes join in S29 (I-01-T23).
- **The projector** (`project`, `practice.api.SUBSCRIPTIONS`): one row per event, built from the
  event's identifiers and the engagement's client and office (read from `engagements`, under the
  event's tenant as the system), inserted with `source_event_id` = the event id and `ON CONFLICT
  DO NOTHING`: a redelivered or replayed event changes nothing, and writes no audit event. Rows
  hold identifiers, codes and counts only (`facts`); no names, amounts or free text.
- **Rebuild** (`rebuild_home_activity`, `abacus_tools.reproject_home_activity`): the firm's
  published allowlisted events of the last 90 days, read through the relay role, projected again;
  rows already there are untouched.
- **Prune** (`prune_once`, `HomeActivityPruneWorkflow` on `home_activity_prune:platform`, daily):
  rows older than 90 days on each firm's business clock are deleted, firm by firm.
- **Read** (`client_activity`): the newest 20 rows the viewer may read under
  `visible(engagement.read_metadata)` (walls leave the client out entirely, DEC-43), narrowed by
  office (DEC-30, a filter only); client and actor labels resolved now, never stored.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, OutboxEvent, Ref, Target, uow
from abacus.kernel.uow.relay import published_events
from abacus.modules.engagements.api import engagement_hold_facts, gate_offices
from abacus.modules.identity.api import AuthContext, firm_tenant_ids, names_of, visible
from abacus.modules.organisations.api import firm_names
from abacus.modules.practice.models import HomeActivityItem

_log = get_logger(__name__)

RETENTION: Final = timedelta(days=90)
LIMIT: Final = 20  # HOME-01 shows the first 20 (home-and-gates.md §3)
READ_ACTION: Final = "engagement.read_metadata"
ACTIVITY_TYPES: Final = frozenset(
    {"client_upload", "follow_up_sent", "letter_recorded", "agent_pre_screen"}
)


@dataclass(frozen=True)
class Shape:
    """What one event becomes: its activity code, actor and subject, and its facts."""

    event_type: str
    actor_kind: str
    actor_ref: dict[str, str]
    subject_ref: dict[str, str]
    facts: dict[str, str | int | bool]


def _id(payload: dict[str, object], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    return str(UUID(str(raw)))  # identifiers only: anything else fails the event


def _upload(p: dict[str, object]) -> Shape | None:
    item, by = _id(p, "request_item_id"), _id(p, "uploaded_by")
    if item is None or by is None:
        return None
    return Shape(
        "client_upload",
        "contact",
        {"type": "contact", "id": by},
        {"type": "request_item", "id": item},
        {"count": 1},
    )


def _follow_up(p: dict[str, object]) -> Shape | None:
    follow_up, by = _id(p, "follow_up_id"), _id(p, "sent_by")
    if follow_up is None or by is None:
        return None
    return Shape(
        "follow_up_sent",
        "user",
        {"type": "user", "id": by},
        {"type": "follow_up", "id": follow_up},
        {},
    )


def _letter(p: dict[str, object]) -> Shape | None:
    if p.get("gate") != "G3":
        return None  # G1 and G2 are not client activity
    engagement = _id(p, "engagement_id")
    if engagement is None:
        return None
    return Shape(
        "letter_recorded",
        "system",
        {"type": "system"},
        {"type": "engagement", "id": engagement},
        {"gate": "G3"},
    )


def _pre_screen(p: dict[str, object]) -> Shape | None:
    version = _id(p, "evidence_version_id")
    if version is None:
        return None
    return Shape(
        "agent_pre_screen",
        "agent_run",
        {"type": "agent_run"},
        {"type": "evidence_version", "id": version},
        {},
    )


SOURCES: Final[dict[str, Callable[[dict[str, object]], Shape | None]]] = {
    "evidence.uploaded": _upload,
    "follow_up.sent": _follow_up,
    "gate.met": _letter,
    "upload_review.recorded": _pre_screen,
}


def _system(tenant_id: UUID, purpose: str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"home_activity:{purpose}")


async def _insert(event: OutboxEvent, occurred_at: datetime | None) -> int:
    """One event's row, or nothing (not allowlisted, not shaped, unknown engagement, already
    there). Returns the rows inserted (0 or 1)."""
    shape_of = SOURCES.get(event.event_type)
    if shape_of is None:
        return 0
    shape = shape_of(event.payload)
    engagement_raw = event.payload.get("engagement_id")
    if shape is None or engagement_raw is None:
        return 0
    engagement_id = UUID(str(engagement_raw))
    tenant = _system(event.tenant_id, "project")
    facts = await engagement_hold_facts(tenant, engagement_id)
    if facts is None:
        return 0
    offices = await gate_offices(tenant, [(engagement_id, None)])
    when = occurred_at if occurred_at is not None else await clock.now(tenant)
    try:
        async with uow(tenant) as tx:
            found = await tx.session.execute(
                pg_insert(HomeActivityItem)
                .values(
                    tenant_id=event.tenant_id,
                    source_event_id=event.event_id,
                    event_type=shape.event_type,
                    occurred_at=when,
                    client_id=facts.client_id,
                    engagement_id=engagement_id,
                    work_item_id=None,
                    office_id=offices.get((engagement_id, None)),
                    actor_kind=shape.actor_kind,
                    actor_ref=shape.actor_ref,
                    subject_ref=shape.subject_ref,
                    facts=shape.facts,
                )
                .on_conflict_do_nothing(constraint="home_activity_items_once")
                .returning(HomeActivityItem.id)
            )
            added = len(found.scalars().all())
            if added:
                tx.record(
                    "home_activity.projected",
                    target=Target("engagement", engagement_id),
                    after=Ref(event_type=shape.event_type),
                )
            return added
    except MissingAuditEvent:
        return 0  # a replay: the row was already there, nothing written


async def project(event: OutboxEvent) -> None:
    """The `HomeActivityProjector` outbox consumer: idempotent on the event id."""
    await _insert(event, None)


async def rebuild_home_activity(tenant_id: UUID) -> int:
    """`practice.rebuild_home_activity`: the firm's published allowlisted events of the last 90
    days, projected again; returns the rows inserted (0 on a projection already whole)."""
    since = await clock.now(_system(tenant_id, "rebuild")) - RETENTION
    added = 0
    for event, occurred_at in await published_events(tenant_id, tuple(SOURCES), since):
        added += await _insert(event, occurred_at)
    return added


async def prune_firm(tenant_id: UUID) -> int:
    """One firm: rows older than 90 days on its business clock go; how many."""
    tenant = _system(tenant_id, "prune")
    cutoff = await clock.now(tenant) - RETENTION
    try:
        async with uow(tenant) as tx:
            gone = await tx.session.execute(
                delete(HomeActivityItem)
                .where(HomeActivityItem.occurred_at < cutoff)
                .returning(HomeActivityItem.id)
            )
            count = len(gone.scalars().all())
            if count:
                tx.record(
                    "home_activity.pruned",
                    target=Target("retention", RETENTION.days),
                    after=Ref(count=count),
                )
            return count
    except MissingAuditEvent:
        return 0  # nothing was old enough in this firm


async def prune_once() -> int:
    """Every firm; one firm's failure is logged by id and the others still run."""
    total = 0
    for tenant_id in await firm_tenant_ids():
        try:
            total += await prune_firm(tenant_id)
        except Exception as exc:
            _log.error(
                "home_activity.prune_failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    _log.info("home_activity.pruned", count=total)
    return total


# --- read ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ActivityRow:
    item: HomeActivityItem
    client_label: str
    actor_label: str | None


async def client_activity(
    ctx: AuthContext, office_id: UUID | None, limit: int = LIMIT
) -> list[ActivityRow]:
    """AC4.3, AC4.4: the newest rows the viewer may read, walls applied in the query, office a
    filter only; labels resolved now."""
    query = (
        select(HomeActivityItem)
        .where(visible(ctx, READ_ACTION, HomeActivityItem.engagement_id))
        .order_by(HomeActivityItem.occurred_at.desc(), HomeActivityItem.id)
        .limit(limit)
    )
    if office_id is not None:
        query = query.where(HomeActivityItem.office_id == office_id)
    async with tenant_session(ctx.tenant) as session:
        items: Sequence[HomeActivityItem] = (await session.execute(query)).scalars().all()
    if not items:
        return []
    clients = {n.client_id: n.name for n in await firm_names(ctx.tenant) if n.id == n.client_id}
    people = [
        UUID(i.actor_ref["id"])
        for i in items
        if i.actor_kind in ("user", "contact") and "id" in i.actor_ref
    ]
    names = await names_of(sorted(set(people), key=str)) if people else {}
    return [
        ActivityRow(
            i,
            clients.get(i.client_id, ""),
            names.get(UUID(i.actor_ref["id"])) if "id" in i.actor_ref else None,
        )
        for i in items
    ]


__all__ = [
    "ACTIVITY_TYPES",
    "LIMIT",
    "RETENTION",
    "SOURCES",
    "ActivityRow",
    "client_activity",
    "project",
    "prune_firm",
    "prune_once",
    "rebuild_home_activity",
]
