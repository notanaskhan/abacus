"""The knowledge embedding workflow (SPEC-009 AC-6; ADR-017, ADR-090). PROTECTED.

Started by the relay for each `knowledge_document.added`
(`knowledge-embed:<tenant_id>:<document_id>`), in the batch class. Orchestration only: activities
by name, identifiers in and out (WF-001). It embeds batches until the document is ready or no
longer pending; a call not yet admitted waits and asks again; a provider that stays unavailable
fails the document with a fixed code. Changes are guarded with `workflow.patched(...)`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.workflow_types import (
        PROVIDER_UNAVAILABLE,
        BatchOutcome,
        FailKnowledgeInput,
        KnowledgeInput,
    )

_TIMEOUT = timedelta(minutes=2)
_MAX_WAIT_SECONDS = 300
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=6,
)
_FAIL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)


@workflow.defn(name="knowledge-embedding")
class KnowledgeEmbeddingWorkflow:
    @workflow.run
    async def run(self, input: KnowledgeInput) -> str:
        while True:
            try:
                outcome = await workflow.execute_activity(
                    "knowledge.embed_batch",
                    input,
                    result_type=BatchOutcome,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except ActivityError:
                await workflow.execute_activity(
                    "knowledge.fail",
                    FailKnowledgeInput(input.tenant_id, input.document_id, PROVIDER_UNAVAILABLE),
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_FAIL_RETRY,
                )
                return "failed"
            if outcome.done:
                return "done"
            if outcome.wait_seconds > 0:
                await workflow.sleep(
                    timedelta(seconds=min(outcome.wait_seconds, _MAX_WAIT_SECONDS))
                )
