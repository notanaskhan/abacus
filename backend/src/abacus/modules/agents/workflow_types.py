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
class MatchInput:
    """SPEC-033 (TASK-066): a matcher run for one inbox file, on behalf of `requested_by` (the
    engagement partner, or the person who asked)."""

    tenant_id: str
    inbox_file_id: str
    event_id: str
    requested_by: str | None


@dataclass(frozen=True)
class MatchRunInput:
    tenant_id: str
    run_id: str
    inbox_file_id: str


@dataclass(frozen=True)
class IntakeMatchInput:
    """N-01-T22: the matcher's intake mode for one intake attachment of a matched client, on
    behalf of the client's relationship partner (code resolves them; the event names neither)."""

    tenant_id: str
    attachment_id: str
    client_id: str
    event_id: str


@dataclass(frozen=True)
class IntakeMatchRunInput:
    tenant_id: str
    run_id: str
    attachment_id: str


@dataclass(frozen=True)
class GuidanceDraftInput:
    """SPEC-035 (TASK-073): one guidance drafter run for one request item, for `requested_by`."""

    tenant_id: str
    engagement_id: str
    request_item_id: str
    event_id: str
    requested_by: str
    # TASK-074: a template item instead (engagement and request item empty).
    methodology_version_id: str = ""
    position: int = -1


@dataclass(frozen=True)
class GuidanceDraftRunInput:
    tenant_id: str
    run_id: str
    request_item_id: str
    position: int = -1  # TASK-074: the template item, when `request_item_id` is empty


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


@dataclass(frozen=True)
class NextTickInput:
    """SPEC-027 (TASK-051): whose time zone sets the agent's daily tick."""

    tenant_id: str


@dataclass(frozen=True)
class EntryAssessInput:
    """SPEC-037 Q4 (TASK-085): one entry assessor run on a selected entry, for `requested_by`."""

    tenant_id: str
    engagement_id: str
    selected_item_id: str
    event_id: str
    requested_by: str


@dataclass(frozen=True)
class EntryAssessRunInput:
    tenant_id: str
    run_id: str
    selected_item_id: str


# --- A-04-T11: the section drafter (identifiers in and out, WF-001; DEC-1868) -------------------


@dataclass(frozen=True)
class SectionDraftInput:
    """One section drafter run, created when a person chose Draft with agent. The run row holds
    the engagement and the initiator; the paper must be that engagement's."""

    tenant_id: str
    run_id: str
    workpaper_id: str
    mode: str
    section_key: str  # "" for the whole paper


# --- K-01-T21: the methodology importer (identifiers in and out, WF-001) -------------------------


@dataclass(frozen=True)
class MethodologyImportInput:
    """One import's document parse, started by `requested_by` from `POST …/imports/{id}/start`."""

    tenant_id: str
    import_id: str
    requested_by: str


@dataclass(frozen=True)
class ImportPagesOutcome:
    """`page_count` pages read in the isolated child; `held` when the PII hold stopped it."""

    page_count: int
    held: bool


@dataclass(frozen=True)
class ImportBatchInput:
    tenant_id: str
    import_id: str
    requested_by: str
    first_page: int
    last_page: int
    # The previous batch's run: the program in force on this batch's context page (end review).
    previous_run_id: str | None = None


@dataclass(frozen=True)
class ImportBatchOutcome:
    """The batch's run, or `stop` when the import was cancelled or a terminal error ended it."""

    run_id: str | None
    stop: bool


@dataclass(frozen=True)
class ImportFinishInput:
    tenant_id: str
    import_id: str
    run_ids: list[str]


@dataclass(frozen=True)
class ImportFailInput:
    tenant_id: str
    import_id: str
    code: str
