"""Workflow and activity payloads for retrieval (TASK-010 design §6, revision 1). Identifiers
only.

Plain dataclasses of strings, so they serialise stably (replay, ADR-090). The workflow input is
never proof of anything: every activity re-derives its context from the run row.
"""

from __future__ import annotations

from dataclasses import dataclass

# Error types carried from activities to the workflow (ApplicationError.type).
RUN_FAILED = "RunFailed"
UNAVAILABLE = "Unavailable"
FORBIDDEN_ERROR = "Forbidden"  # identity's Forbidden, e.g. a wall on the person (SPEC-002 AC-7)
# What a workflow-level failure may record (anything else becomes INTERNAL_ERROR).
FAIL_STATUSES = frozenset({"failed", "failed_validation"})
PROVIDER_UNAVAILABLE = "provider_unavailable"
INTERNAL_ERROR = "internal_error"
CANCELLED = "cancelled"
FORBIDDEN = "forbidden"
FAIL_CODES = frozenset({PROVIDER_UNAVAILABLE, INTERNAL_ERROR, CANCELLED, FORBIDDEN})


@dataclass(frozen=True)
class RetrievalInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class FailInput:
    tenant_id: str
    run_id: str
    status: str
    code: str


@dataclass(frozen=True)
class RetrievalOutcome:
    status: str
    code: str | None = None
    evidence_version_id: str | None = None
