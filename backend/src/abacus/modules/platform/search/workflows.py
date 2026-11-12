"""SearchReindexWorkflow and SearchDriftCheckWorkflow (P-02-T06; P-02 §4.5; ADR-241; DEC-4612).

Orchestration only, activities by name, identifiers only in the history (tenant ids, object types,
object ids, cursors, counts; never a title). Both run on the `batch` class and hold no slot longer
than one batch. Changes land behind `workflow.patched(...)`;
`tests/workflows/histories/search-reindex-v1-*.json` must keep replaying.

- **Reindex** `search_reindex:<tenant>:<type|all>[:<client>]`: listed ids are indexed in pages of
  500; otherwise each registered type (or the one named) is paged through its owner's lister
  (or the rows already indexed) and each page is rebuilt. Idempotent under replay: each page
  rebuilds from current state, so a retried page writes the same rows. The last activity audits
  `search_index.reindex_completed` with the counts.
- **Drift check** (the nightly schedule): for every firm and type, rebuild a 1 % sample (at least
  one, at most 200 ids) and compare the builder's hash with the stored row; mismatches are
  reindexed and counted on `abacus.search.drift`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

PAGE = 500
_STEP = timedelta(minutes=5)
_RETRY = RetryPolicy(maximum_attempts=5, maximum_interval=timedelta(minutes=2))
SEARCH_DRIFT_ID = "search_drift:platform"


@dataclass(frozen=True)
class ReindexInput:
    tenant_id: str
    object_type: str | None = None  # None: every registered type
    client_id: str | None = None
    ids: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class ReindexPage:
    """A page of ids for one type, and the cursor the next page starts after."""

    object_type: str
    ids: list[str]
    next_cursor: str | None


@workflow.defn(name="SearchReindexWorkflow")
class SearchReindexWorkflow:
    @workflow.run
    async def run(self, request: ReindexInput) -> int:
        indexed = 0
        if request.ids:
            object_type = request.object_type or ""  # listed ids always name their type
            for start in range(0, len(request.ids), PAGE):
                indexed += await self._index(
                    request, object_type, request.ids[start : start + PAGE]
                )
        else:
            types: list[str] = await workflow.execute_activity(
                "platform.search_reindex_types",
                args=[request],
                result_type=list[str],
                start_to_close_timeout=_STEP,
                retry_policy=_RETRY,
            )
            for object_type in types:
                cursor: str | None = None
                while True:
                    page: ReindexPage = await workflow.execute_activity(
                        "platform.search_list_ids",
                        args=[request, object_type, cursor],
                        result_type=ReindexPage,
                        start_to_close_timeout=_STEP,
                        retry_policy=_RETRY,
                    )
                    indexed += await self._index(request, object_type, page.ids)
                    if page.next_cursor is None:
                        break
                    cursor = page.next_cursor
        await workflow.execute_activity(
            "platform.search_reindex_completed",
            args=[request, indexed],
            start_to_close_timeout=_STEP,
            retry_policy=_RETRY,
        )
        return indexed

    async def _index(self, request: ReindexInput, object_type: str, ids: list[str]) -> int:
        if not ids:
            return 0
        done: int = await workflow.execute_activity(
            "platform.search_index_batch",
            args=[request.tenant_id, object_type, ids],
            result_type=int,
            start_to_close_timeout=_STEP,
            retry_policy=_RETRY,
        )
        return done


@workflow.defn(name="SearchDriftCheckWorkflow")
class SearchDriftCheckWorkflow:
    @workflow.run
    async def run(self) -> int:
        drifted: int = await workflow.execute_activity(
            "platform.search_drift_check",
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_RETRY,
        )
        return drifted
