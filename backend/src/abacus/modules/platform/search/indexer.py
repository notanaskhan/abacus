"""The SearchIndexer (P-02-T06; P-02 §4.5, §4.6; ADR-241 decisions 3 and 9; DEC-4612).

An outbox consumer composed from the registered projections' triggers: each trigger maps an
event's identifier-only payload to the ids it reindexes, and each id is rebuilt from the owner's
current state through its builder (so relay order and replays never matter: idempotent on the
object, not the event). A builder answering None deletes the row (a withdrawn or destroyed record,
or one no longer findable). More than `FANOUT` ids from one event (a client rename touching its
returns, audits, binders and documents) start a `SearchReindexWorkflow` instead of an inline pass.

Every built document is scrubbed (`scrub.scrub_document`, P-02-T07) and checked against the
contract (`spec.check_document`) before it is stored. A document that fails is not stored and the
previous row is deleted rather than left stale; the failure is logged by type and id only, never
by content. Walls are not subscribed to: they are evaluated at query time (P-02 §4.6).

**Lag (P-02-T13, DEC-4726).** On the relay path only (an outbox event, not a reindex backfill),
each stored document's lag from its source change (`source_updated_at`) to now is recorded on the
`abacus.search.index_lag` histogram and logged as `search.index_lag` (`lag_ms`, `object_type`:
identifiers only). CloudWatch's log metric filter turns the line into `SearchIndexLagMs`, alarmed
at p95 above 5 s (`infra/modules/search`, RB-31). The target is P-02's relay lag p95 ≤ 5 s.

`membership.deactivated` purges that person's recents. The reindex is audited
(`search_index.reindex_requested` here, `.reindex_completed` by the workflow's last activity).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from datetime import datetime
from typing import Final
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import dispatch
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.platform.search import store
from abacus.modules.platform.search.scrub import scrub_document
from abacus.modules.platform.search.spec import (
    SearchProjection,
    SearchRegistrationInvalid,
    check_document,
    projection,
    projections,
)
from abacus.modules.platform.search.workflows import (
    ReindexInput,
    SearchReindexWorkflow,
)


def reindex_workflow_id(tenant_id: UUID, object_type: str | None, client_id: UUID | None) -> str:
    """The reindex workflow's id: one per firm, object type and client (dedupes requests)."""
    base = f"search_reindex:{tenant_id}:{object_type or 'all'}"
    return base if client_id is None else f"{base}:{client_id}"


FANOUT: Final = 200  # ids from one event above this go to the workflow (P-02 §4.6)
MEMBERSHIP_DEACTIVATED: Final = "membership.deactivated"
_log = get_logger("abacus.search.indexer")

Handler = Callable[[OutboxEvent], Awaitable[None]]


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", store.ACTOR)


_lag = meter(__name__).create_histogram(
    "abacus.search.index_lag", unit="s", description="Source change to stored search document"
)
LAG_TARGET_SECONDS: Final = 5.0


def record_lag(object_type: str, source_updated_at: datetime) -> float:
    """The relay-path lag in seconds (never negative), on the histogram and the log line."""
    seconds = max(0.0, (system_now() - source_updated_at).total_seconds())
    _lag.record(seconds)
    _log.info("search.index_lag", object_type=object_type, lag_ms=round(seconds * 1000))
    return seconds


async def index_object(
    tenant_id: UUID, object_type: str, object_id: UUID, *, relay: bool = False
) -> str:
    """Rebuild one object's row: `indexed`, `deleted`, `refused` (contract) or `unregistered`.
    `relay` marks an outbox-driven rebuild, whose lag is measured (module docstring)."""
    found = projection(object_type)
    if found is None:
        return "unregistered"
    doc = await found.build(_system(tenant_id), object_id)
    if doc is None:
        await store.delete(tenant_id, object_type, object_id)
        return "deleted"
    doc = scrub_document(doc)
    try:
        check_document(found, doc)
    except SearchRegistrationInvalid:
        _log.warning("search.document_refused", object_type=object_type, object_id=str(object_id))
        await store.delete(tenant_id, object_type, object_id)
        return "refused"
    await store.upsert(tenant_id, found, doc)
    if relay:
        record_lag(object_type, doc.source_updated_at)
    return "indexed"


async def index_many(
    tenant_id: UUID, object_type: str, ids: Iterable[UUID], *, relay: bool = False
) -> dict[str, int]:
    out: dict[str, int] = {}
    for object_id in ids:
        result = await index_object(tenant_id, object_type, object_id, relay=relay)
        out[result] = out.get(result, 0) + 1
    return out


async def request_reindex(
    tenant_id: UUID,
    object_type: str | None,
    *,
    client_id: UUID | None = None,
    ids: tuple[UUID, ...] = (),
    actor: str = store.ACTOR,
) -> str:
    """Audit and start one reindex run (all types, one type, one client's, or listed ids); the id
    reuse policy attaches a second request to the run in flight."""
    tenant = TenantContext(tenant_id, "system", actor)
    async with uow(tenant) as tx:
        tx.record(
            "search_index.reindex_requested",
            target=Target("search_index", tenant_id),
            after=Ref(object_type=object_type or "all", ids=len(ids)),
        )
    run_id = reindex_workflow_id(tenant_id, object_type, client_id)
    await dispatch(
        SearchReindexWorkflow,
        ReindexInput(
            tenant_id=str(tenant_id),
            object_type=object_type,
            client_id=None if client_id is None else str(client_id),
            ids=[str(i) for i in ids],
        ),
        id=run_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


def _handler(event_type: str, targets: tuple[SearchProjection, ...]) -> Handler:
    async def handle(event: OutboxEvent) -> None:
        for target in targets:
            trigger = target.triggers[event_type]
            ids = tuple(dict.fromkeys(trigger(event.payload)))
            if len(ids) > FANOUT:
                await request_reindex(event.tenant_id, target.object_type, ids=ids)
            else:
                await index_many(event.tenant_id, target.object_type, ids, relay=True)

    return handle


async def _membership_deactivated(event: OutboxEvent) -> None:
    raw = event.payload.get("user_id")
    if raw is not None:
        await store.purge_recents(event.tenant_id, [UUID(str(raw))])


class SearchSubscriptions(Mapping[str, Handler]):
    """`SUBSCRIPTIONS`, read when the worker composes them (after every owner registered its
    projection, the `reporting.api` precedent): one handler per trigger event type."""

    def _events(self) -> dict[str, tuple[SearchProjection, ...]]:
        out: dict[str, list[SearchProjection]] = {}
        for registered in projections():
            for event_type in registered.triggers:
                out.setdefault(event_type, []).append(registered)
        return {k: tuple(v) for k, v in out.items()}

    def __getitem__(self, event_type: str) -> Handler:
        if event_type == MEMBERSHIP_DEACTIVATED:
            return _membership_deactivated
        return _handler(event_type, self._events()[event_type])

    def __iter__(self) -> Iterator[str]:
        events = self._events()
        return iter((MEMBERSHIP_DEACTIVATED, *(e for e in events if e != MEMBERSHIP_DEACTIVATED)))

    def __len__(self) -> int:
        return len(set(self._events()) | {MEMBERSHIP_DEACTIVATED})


SUBSCRIPTIONS: Final = SearchSubscriptions()

__all__ = ["FANOUT", "SUBSCRIPTIONS", "index_many", "index_object", "request_reindex"]
