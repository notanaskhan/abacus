"""Screening workflow and activity payloads (TASK-011 design §7). Identifiers only.

Plain dataclasses of strings, so they serialise stably (replay, ADR-090). The workflow input is
never proof of anything: activities re-derive the agent's context from its run row.
"""

from __future__ import annotations

from dataclasses import dataclass

# What the workflow may record when it ends a run (anything else becomes INTERNAL_ERROR).
PROVIDER_UNAVAILABLE = "provider_unavailable"
INTERNAL_ERROR = "internal_error"
CANCELLED = "cancelled"
# Waited for a work slot longer than the class allows (SPEC-003 AC-14).
CAPACITY_TIMEOUT = "capacity_timeout"
# The model call wasn't admitted (SPEC-003 AC-11): ApplicationError type, with details
# (reason, retry_after seconds, the class's maximum wait in seconds).
NOT_ADMITTED = "NotAdmitted"
FAIL_CODES = frozenset({PROVIDER_UNAVAILABLE, INTERNAL_ERROR, CANCELLED, CAPACITY_TIMEOUT})


@dataclass(frozen=True)
class ScreeningInput:
    """From the relayed `evidence_version.created` event: the only source of `requested_by`."""

    tenant_id: str
    evidence_version_id: str
    event_id: str
    requested_by: str | None


@dataclass(frozen=True)
class RunInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class FailInput:
    tenant_id: str
    run_id: str
    code: str


@dataclass(frozen=True)
class ScreeningOutcome:
    """`skipped` (no run: nobody to act for, or not a screenable version), or the run's final
    status (`completed`, `escalated`, `failed`)."""

    status: str
    run_id: str | None = None
    code: str | None = None
    screening_result_id: str | None = None


@dataclass(frozen=True)
class SlotGrant:
    """An `acquire_slot` activity's answer (SPEC-003): granted, and the class's maximum wait in
    seconds before the run fails `capacity_timeout`."""

    granted: bool
    max_wait_seconds: int


# --- Knowledge embedding (SPEC-009; TASK-024 design §7) ----------------------------------------


@dataclass(frozen=True)
class KnowledgeInput:
    """From the relayed `knowledge_document.added` event."""

    tenant_id: str
    document_id: str


@dataclass(frozen=True)
class BatchOutcome:
    done: bool  # ready, failed, or no longer pending: the workflow ends
    wait_seconds: int = 0  # > 0: not admitted yet; ask again after this


@dataclass(frozen=True)
class FailKnowledgeInput:
    tenant_id: str
    document_id: str
    code: str


# --- The engagement agent (SPEC-027; TASK-050) ---------------------------------------------------


@dataclass(frozen=True)
class AgentInput:
    """One engagement's agent: `engagement-agent:<tenant_id>:<engagement_id>`."""

    tenant_id: str
    engagement_id: str


@dataclass(frozen=True)
class AgentEvent:
    """A relayed domain event (or a resume) for the agent: its type, id and identifiers only."""

    event_type: str
    event_id: str
    payload: dict[str, str]


@dataclass(frozen=True)
class HandleInput:
    tenant_id: str
    engagement_id: str
    event_type: str
    event_id: str
    payload: dict[str, str]


@dataclass(frozen=True)
class HandleResult:
    """`end`: the engagement is archived (or gone), so the agent's work is over."""

    end: bool
