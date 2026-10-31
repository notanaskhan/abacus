"""MethodologyImportWorkflow (`methodology-import-v1`; K-01-T21; K-01 §4.4; ADR-090). PROTECTED.

Started by `POST /v1/methodology/imports/{id}/start` for an import with a PDF (the methodology
module's document-importer slot), in the background class. Orchestration only: activities
by name, identifiers in and out (WF-001): it extracts the pages (the PII hold may end it
there), parses
batches of eight pages, each a run of its own, stopping when the import is cancelled or a batch
fails it, then verifies and writes the version for review. Changes ship behind
`workflow.patched(...)` with a replay history.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.workflow_types import (
        ImportBatchInput,
        ImportBatchOutcome,
        ImportFailInput,
        ImportFinishInput,
        ImportPagesOutcome,
        MethodologyImportInput,
    )

BATCH_PAGES = 8
_EXTRACT_TIMEOUT = timedelta(minutes=5)
_BATCH_TIMEOUT = timedelta(minutes=4)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=4,
)
_FAIL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)


@workflow.defn(name="methodology-import-v1")
class MethodologyImportWorkflow:
    @workflow.run
    async def run(self, input: MethodologyImportInput) -> str:
        try:
            pages = await workflow.execute_activity(
                "methodology.extract_pages",
                input,
                result_type=ImportPagesOutcome,
                start_to_close_timeout=_EXTRACT_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await self._fail(input, "extract_failed")
            return "failed"
        if pages.held:
            return "held"
        run_ids: list[str] = []
        for first in range(1, pages.page_count + 1, BATCH_PAGES):
            last = min(first + BATCH_PAGES - 1, pages.page_count)
            try:
                outcome = await workflow.execute_activity(
                    "agents.importer_parse_batch",
                    ImportBatchInput(
                        input.tenant_id, input.import_id, input.requested_by, first, last
                    ),
                    result_type=ImportBatchOutcome,
                    start_to_close_timeout=_BATCH_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                await self._fail(input, "provider_unavailable")
                return "failed"
            if outcome.stop:
                return "stopped"
            if outcome.run_id is not None:
                run_ids.append(outcome.run_id)
        try:
            return await workflow.execute_activity(
                "methodology.finish_import",
                ImportFinishInput(input.tenant_id, input.import_id, run_ids),
                result_type=str,
                start_to_close_timeout=_EXTRACT_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await self._fail(input, "finish_failed")
            return "failed"

    async def _fail(self, input: MethodologyImportInput, code: str) -> None:
        await workflow.execute_activity(
            "methodology.fail_import",
            ImportFailInput(input.tenant_id, input.import_id, code),
            start_to_close_timeout=_BATCH_TIMEOUT,
            retry_policy=_FAIL_RETRY,
        )
