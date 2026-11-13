"""The run trace's sample resolvers for records other modules own (P-09-T08; WB-09 a2).

`trace.samples_for` resolves a step's `sample_refs` per record type through
`register_trace_samples` and fails closed for a type with no resolver. agents depends on
engagements, requests and evidence, so their resolvers are registered here, each module
answering only the ids the reader may see (`visible()`, walls). A record type no module answers
for (trial balance lines, knowledge passages, tax records) keeps showing no samples.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from abacus.modules.agents.trace import Sample, register_trace_samples
from abacus.modules.engagements.api import TraceSampleRow, engagement_trace_samples
from abacus.modules.evidence.api import evidence_item_trace_samples, evidence_version_trace_samples
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import request_item_trace_samples

Reader = Callable[[AuthContext, Sequence[UUID]], Awaitable[list[TraceSampleRow]]]


def _resolver(
    record_type: str, read: Reader
) -> Callable[[AuthContext, Sequence[UUID]], Awaitable[list[Sample]]]:
    async def resolve(ctx: AuthContext, ids: Sequence[UUID]) -> list[Sample]:
        return [Sample(record_type, r.id, r.label, r.open_route) for r in await read(ctx, ids)]

    resolve.__qualname__ = f"resolve_{record_type}"
    return resolve


READERS: dict[str, Reader] = {
    "engagement": engagement_trace_samples,
    "request_item": request_item_trace_samples,
    "evidence_version": evidence_version_trace_samples,
    "evidence_item": evidence_item_trace_samples,
}


_registered = False


def register() -> None:
    """Once per process (agents.api calls it at import)."""
    global _registered
    if _registered:
        return
    for record_type, read in READERS.items():
        register_trace_samples(record_type, _resolver(record_type, read))
    _registered = True
