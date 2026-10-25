"""Public interface of the evidence module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.uow import Handler
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence.activities import ACTIVITIES as UPLOAD_ACTIVITIES
from abacus.modules.evidence.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.evidence.citations.matching import (
    cell_reason as citation_cell_reason,
)
from abacus.modules.evidence.citations.matching import (
    cell_text as citation_cell_text,
)
from abacus.modules.evidence.citations.matching import (
    column_letters,
    page_quote_reason,
    quote_in,
)
from abacus.modules.evidence.citations.matching import normalised as normalised_text
from abacus.modules.evidence.citations.moved import (
    mark_sources_superseded,
    on_version_created,
    on_version_withdrawn,
)
from abacus.modules.evidence.citations.registry import Anchor as CitationAnchor
from abacus.modules.evidence.citations.registry import (
    CitationClaim,
    CitationKind,
    register_citable,
)
from abacus.modules.evidence.citations.registry import Display as CitationLabel
from abacus.modules.evidence.citations.registry import Verdict as CitationVerdict
from abacus.modules.evidence.citations.service import RecordedCitation, record_citations
from abacus.modules.evidence.contract import withdrawal_router
from abacus.modules.evidence.drops import drop_batch
from abacus.modules.evidence.drops_contract import drops_router
from abacus.modules.evidence.events import (
    EvidenceVersionCreated,
    EvidenceVersionWithdrawn,
    InboxFileAdded,
    InboxFileExtracted,
    UploadChecksRecorded,
)
from abacus.modules.evidence.firm_export_contract import router as firm_export_router
from abacus.modules.evidence.gate_facts import decided_among, waiting_among
from abacus.modules.evidence.hold_activities import ACTIVITIES as HOLD_ACTIVITIES
from abacus.modules.evidence.hold_routes import router as legal_hold_router
from abacus.modules.evidence.hold_runs import SUBSCRIPTIONS as HOLD_SUBSCRIPTIONS
from abacus.modules.evidence.hold_runs import WORKFLOWS as HOLD_WORKFLOWS
from abacus.modules.evidence.hold_runs import with_hold_inheritance
from abacus.modules.evidence.holds import holds_covering
from abacus.modules.evidence.inbox import add_to_inbox, register_match_picks
from abacus.modules.evidence.match_material import (
    Candidate,
    MatchMaterial,
    match_material,
    worth_matching,
)
from abacus.modules.evidence.matching import MIN_SCORE as SUGGESTION_MIN_SCORE
from abacus.modules.evidence.matching import suggest as suggest_by_name
from abacus.modules.evidence.portal_files import (
    PortalFile,
    SentBack,
    client_pre_checks,
    portal_files,
)
from abacus.modules.evidence.processing import (
    SUBSCRIPTIONS as UPLOAD_SUBSCRIPTIONS,
)
from abacus.modules.evidence.processing import (
    WORKFLOWS as UPLOAD_WORKFLOWS,
)
from abacus.modules.evidence.processing import (
    ReviewMaterial,
    process_upload,
    review_material,
    stale_pdfs,
)
from abacus.modules.evidence.processing import check_upload as check_upload_content
from abacus.modules.evidence.records import RecordClass, StoredRecord, anchor_chain, put_record
from abacus.modules.evidence.render import (
    CODE_COLUMN,
    CREDIT_COLUMN,
    DEBIT_COLUMN,
    FIRST_LINE_ROW,
    NAME_COLUMN,
    TOTAL_LABEL,
    TrialBalance,
    TrialBalanceLine,
    render_trial_balance,
)
from abacus.modules.evidence.render import (
    MEDIA_TYPE as XLSX_MEDIA_TYPE,
)
from abacus.modules.evidence.render_gl import (
    GlBalanceRow,
    GlHeader,
    render_general_ledger,
    render_journal_listing,
)
from abacus.modules.evidence.render_gl import GlEntryRow as GlRenderEntry
from abacus.modules.evidence.retention import RECORD_TYPES, extend_retention_for, retain_until_for
from abacus.modules.evidence.retention_routes import platform_router as retention_platform_router
from abacus.modules.evidence.retention_routes import router as retention_router
from abacus.modules.evidence.routes import firm_router, router

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.evidence.screening_facts import (
    ScreeningFacts,
    screening_facts,
    verified_citation_ids,
)
from abacus.modules.evidence.service import (
    EngagementArchived,
    EvidenceVersionRef,
    EvidenceVersionSummary,
    EvidenceVersionView,
    NewItem,
    Proposal,
    Provenance,
    ScreeningDecision,
    StoredObject,
    UndoneView,
    UndoWindowClosed,
    add_version,
    decisions_on_screenings,
    engagement_snapshots,
    evidence_versions_for,
    read_content,
    read_version,
    register_proposal_source,
    release_member_assignments,
    stage_content,
    undo_review_decision,
    version_view,
)
from abacus.modules.evidence.storage import (
    MAX_CONTENT_BYTES,
    ContentTooLarge,
    IntegrityError,
    check_ready,
)
from abacus.modules.evidence.trust_contract import router as trust_router
from abacus.modules.evidence.upload_facts import upload_facts
from abacus.modules.evidence.uploads import UPLOAD_EDGE_BYTES, UPLOAD_ROUTE_PATHS, upload
from abacus.modules.evidence.withdrawals import ACTIVITIES as WITHDRAWAL_ACTIVITIES
from abacus.modules.evidence.withdrawals import SUBSCRIPTIONS as WITHDRAWAL_SUBSCRIPTIONS
from abacus.modules.evidence.withdrawals import WORKFLOWS as WITHDRAWAL_WORKFLOWS
from abacus.modules.evidence.withdrawals import is_version_withdrawn, withdrawn_among
from abacus.modules.evidence.words import WORDS_VERSION, start_trust_layer_backfill
from abacus.modules.evidence.workflow_types import INBOX as UPLOAD_INBOX
from abacus.modules.evidence.workflow_types import VERSION as UPLOAD_VERSION
from abacus.modules.evidence.workflow_types import (
    BackfillInput,
    LegalHoldInput,
    UploadInput,
    WithdrawalPurgeInput,
)
from abacus.modules.evidence.workflows import (
    EvidenceWithdrawalPurge,
    LegalHoldApply,
    LegalHoldRelease,
    TrustLayerBackfill,
    UploadProcessing,
)
from abacus.modules.identity.api import AbacusRouter, register_member_removed
from abacus.modules.requests.api import register_upload_facts

ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    withdrawal_router,  # C5 v1 stub (P-06-T01; ADR-162)
    drops_router,  # C5 portal-pbc stub (R-01-T01): a portal drop
    trust_router,  # C4 v1 stub (P-03-T02; ADR-144)
    retention_router,  # Q-02-T23: a firm's retention policies
    retention_platform_router,  # Q-02-T23: staff floor and default sets
    legal_hold_router,  # Q-02-T29: legal holds
    firm_export_router,  # Q-02-T38: the firm-export contract stub (Q-02-T43 implements it)
)

# Q-02-T29: the legal-hold workflows and their activities beside upload processing; a new version
# gets its S3 holds before its processing starts. Importing `holds` registered `holds_covering`
# as the kernel's hold check (fail closed without it).
# P-06-T19 (ADR-162 §7): the withdrawal purge, started by `evidence_version.withdrawn`.
WORKFLOWS: dict[type, str] = {**UPLOAD_WORKFLOWS, **HOLD_WORKFLOWS, **WITHDRAWAL_WORKFLOWS}
ACTIVITIES: tuple[object, ...] = (
    *UPLOAD_ACTIVITIES,
    *HOLD_ACTIVITIES,
    *WITHDRAWAL_ACTIVITIES,
)


def in_turn(first: Handler, then: Handler) -> Handler:
    """Two of this module's subscribers on one event, in order (one handler per module)."""

    async def both(event: OutboxEvent) -> None:
        await first(event)
        await then(event)

    return both


_SUBSCRIPTIONS: dict[str, Handler] = {
    **{
        event: (
            with_hold_inheritance(handler)
            if event == EvidenceVersionCreated.event_type
            else handler
        )
        for event, handler in UPLOAD_SUBSCRIPTIONS.items()
    },
    **HOLD_SUBSCRIPTIONS,
    **WITHDRAWAL_SUBSCRIPTIONS,
}
# P-03-T12: the moved and broken detector follows each (both idempotent; a failure retries both).
SUBSCRIPTIONS = {
    **_SUBSCRIPTIONS,
    EvidenceVersionCreated.event_type: in_turn(
        _SUBSCRIPTIONS[EvidenceVersionCreated.event_type], on_version_created
    ),
    EvidenceVersionWithdrawn.event_type: in_turn(
        _SUBSCRIPTIONS[EvidenceVersionWithdrawn.event_type], on_version_withdrawn
    ),
}

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# A-01-T10 (C5 v1.1, DEC-313): a request row's latest upload and the matcher's confidence.
register_upload_facts(upload_facts)

__all__ = [
    "ACTIVITIES",
    "CODE_COLUMN",
    "CREDIT_COLUMN",
    "DEBIT_COLUMN",
    "FIRST_LINE_ROW",
    "MAX_CONTENT_BYTES",
    "NAME_COLUMN",
    "RECORD_TYPES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "SUGGESTION_MIN_SCORE",
    "TOTAL_LABEL",
    "UPLOAD_EDGE_BYTES",
    "UPLOAD_INBOX",
    "UPLOAD_ROUTE_PATHS",
    "UPLOAD_VERSION",
    "WORDS_VERSION",
    "WORKFLOWS",
    "XLSX_MEDIA_TYPE",
    "BackfillInput",
    "Candidate",
    "CitationAnchor",
    "CitationClaim",
    "CitationKind",
    "CitationLabel",
    "CitationVerdict",
    "ContentTooLarge",
    "EngagementArchived",
    "EvidenceVersionCreated",
    "EvidenceVersionRef",
    "EvidenceVersionSummary",
    "EvidenceVersionView",
    "EvidenceVersionWithdrawn",
    "EvidenceWithdrawalPurge",
    "GlBalanceRow",
    "GlHeader",
    "GlRenderEntry",
    "InboxFileAdded",
    "InboxFileExtracted",
    "IntegrityError",
    "LegalHoldApply",
    "LegalHoldInput",
    "LegalHoldRelease",
    "MatchMaterial",
    "NewItem",
    "PortalFile",
    "Proposal",
    "Provenance",
    "RecordClass",
    "RecordedCitation",
    "ReviewMaterial",
    "ScreeningDecision",
    "ScreeningFacts",
    "SentBack",
    "StoredObject",
    "StoredRecord",
    "TrialBalance",
    "TrialBalanceLine",
    "TrustLayerBackfill",
    "UndoWindowClosed",
    "UndoneView",
    "UploadChecksRecorded",
    "UploadInput",
    "UploadProcessing",
    "WithdrawalPurgeInput",
    "add_to_inbox",
    "add_version",
    "anchor_chain",
    "check_ready",
    "check_upload_content",
    "citation_cell_reason",
    "citation_cell_text",
    "client_pre_checks",
    "column_letters",
    "decided_among",
    "decisions_on_screenings",
    "drop_batch",
    "engagement_snapshots",
    "evidence_versions_for",
    "extend_retention_for",
    "firm_router",
    "holds_covering",
    "is_version_withdrawn",
    "mark_sources_superseded",
    "match_material",
    "normalised_text",
    "page_quote_reason",
    "portal_files",
    "process_upload",
    "put_record",
    "quote_in",
    "read_content",
    "read_version",
    "record_citations",
    "register_citable",
    "register_match_picks",
    "register_proposal_source",
    "render_general_ledger",
    "render_journal_listing",
    "render_trial_balance",
    "retain_until_for",
    "review_material",
    "router",
    "screening_facts",
    "stage_content",
    "stale_pdfs",
    "start_trust_layer_backfill",
    "suggest_by_name",
    "undo_review_decision",
    "upload",
    "verified_citation_ids",
    "version_view",
    "waiting_among",
    "withdrawn_among",
    "worth_matching",
]

# SPEC-017 (TASK-032 D2): a removed team member's review assignments go back to the queue.
register_member_removed(release_member_assignments)
