"""`FormExtractionWorkflow` (P-11-T26; P-11 §4.6; ADR-090; DEC-2308). PROTECTED.

Orchestration only, identifiers only (AC7.7): one activity reads, maps and records. `forms.analyze`
(Textract FORMS and TABLES for identified OCR pages) lands with P-11-T27 behind a patch, so these
histories keep replaying. Started by the `evidence_text.ready` subscriber through `kernel.dispatch`
when the firm's `evidence.form_extraction` is on.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.evidence.workflow_types import FormExtractionInput

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=5,
)


@workflow.defn(name="form_extraction")
class FormExtractionWorkflow:
    @workflow.run
    async def run(self, given: FormExtractionInput) -> int:
        return await workflow.execute_activity(
            "forms.extract",
            given,
            result_type=int,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_RETRY,
        )
