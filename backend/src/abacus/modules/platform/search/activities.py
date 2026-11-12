"""The search reindex and drift-check activities (P-02-T06; P-02 §4.5; DEC-4612).

Identifiers in, counts out. Each page rebuilds from the owners' current state (`indexer`), so a
retried activity writes the same rows; the completion activity audits the run once per attempt
that commits (a replayed completion after a commit records nothing new: the unit of work's audit
row is the run's, keyed by the workflow's request).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from temporalio import activity

from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.platform.search import indexer, store
from abacus.modules.platform.search.scrub import scrub_document
from abacus.modules.platform.search.spec import projection, projections
from abacus.modules.platform.search.workflows import PAGE, ReindexInput, ReindexPage

DRIFT_SAMPLE_MAX: Final = 200
_log = get_logger(__name__)
_drift = meter(__name__).create_counter(
    "abacus.search.drift", unit="1", description="Sampled search rows that differed from source"
)


@activity.defn(name="platform.search_reindex_types")
async def search_reindex_types(request: ReindexInput) -> list[str]:
    if request.object_type is not None:
        return [request.object_type] if projection(request.object_type) is not None else []
    return [p.object_type for p in projections()]


@activity.defn(name="platform.search_list_ids")
async def search_list_ids(
    request: ReindexInput, object_type: str, cursor: str | None
) -> ReindexPage:
    tenant_id = UUID(request.tenant_id)
    after = None if cursor is None else UUID(cursor)
    found = projection(object_type)
    if request.client_id is not None:
        ids = await store.indexed_ids_for_client(
            tenant_id, object_type, UUID(request.client_id), after, PAGE
        )
    elif found is not None and found.list_ids is not None:
        ids = await found.list_ids(TenantContext(tenant_id, "system", store.ACTOR), after, PAGE)
    else:
        ids = await store.indexed_ids(tenant_id, object_type, after, PAGE)
    return ReindexPage(
        object_type=object_type,
        ids=[str(i) for i in ids],
        next_cursor=str(ids[-1]) if len(ids) == PAGE else None,
    )


@activity.defn(name="platform.search_index_batch")
async def search_index_batch(tenant_id: str, object_type: str, ids: list[str]) -> int:
    counts = await indexer.index_many(UUID(tenant_id), object_type, (UUID(i) for i in ids))
    return sum(counts.values())


@activity.defn(name="platform.search_reindex_completed")
async def search_reindex_completed(request: ReindexInput, indexed: int) -> None:
    tenant_id = UUID(request.tenant_id)
    async with uow(TenantContext(tenant_id, "system", store.ACTOR)) as tx:
        tx.record(
            "search_index.reindex_completed",
            target=Target("search_index", tenant_id),
            after=Ref(object_type=request.object_type or "all", indexed=indexed),
        )


async def drift_firm(tenant_id: UUID) -> int:
    """One firm: a 1 % sample per type rebuilt and compared; mismatches reindexed."""
    drifted = 0
    tenant = TenantContext(tenant_id, "system", store.ACTOR)
    for registered in projections():
        total = await store.count(tenant_id, registered.object_type)
        if total == 0:
            continue
        n = max(1, min(DRIFT_SAMPLE_MAX, total // 100))
        for object_id in await store.sample(tenant_id, registered.object_type, n):
            doc = await registered.build(tenant, object_id)
            fresh = None if doc is None else store.document_hash(registered, scrub_document(doc))
            if fresh != await store.stored_hash(tenant_id, registered, object_id):
                drifted += 1
                _drift.add(1, {"object_type": registered.object_type})
                await indexer.index_object(tenant_id, registered.object_type, object_id)
    return drifted


@activity.defn(name="platform.search_drift_check")
async def search_drift_check() -> int:
    """Every firm; one firm's failure is logged by id and the others still run."""
    total = 0
    for tenant_id in await firm_tenant_ids():
        try:
            total += await drift_firm(tenant_id)
        except Exception as exc:
            _log.error("search.drift_failed", tenant_id=str(tenant_id), error=type(exc).__name__)
    return total


SEARCH_ACTIVITIES: Final[tuple[object, ...]] = (
    search_reindex_types,
    search_list_ids,
    search_index_batch,
    search_reindex_completed,
    search_drift_check,
)
