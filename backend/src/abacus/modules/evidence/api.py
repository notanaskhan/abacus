"""Public interface of the evidence module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.uow import Handler
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import register_evidence_readable
from abacus.modules.evidence.access import KIND as CONTENT_READ_KIND
from abacus.modules.evidence.activities import ACTIVITIES as UPLOAD_ACTIVITIES
from abacus.modules.evidence.anchor_job import ACTIVITIES as ANCHOR_ACTIVITIES
from abacus.modules.evidence.anchor_job import SCHEDULES as ANCHOR_SCHEDULES
from abacus.modules.evidence.anchor_job import WORKFLOWS as ANCHOR_WORKFLOWS
from abacus.modules.evidence.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.evidence.audit_values import evidence_version_values, pii_reveal_values
from abacus.modules.evidence.citations.display import citation_display
from abacus.modules.evidence.citations.ledger_line import on_trial_balance_version_created
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
from abacus.modules.evidence.classification import (
    ClassifiedIntake,
    classify_intake,
    filed_classification_match,
    record_agent_classification,
    version_with_fingerprint,
)
from abacus.modules.evidence.classifier import rules as classifier_rules
from abacus.modules.evidence.contract import withdrawal_router
from abacus.modules.evidence.drops import drop_batch
from abacus.modules.evidence.drops_contract import drops_router, void_router
from abacus.modules.evidence.duplicates_contract import duplicates_router
from abacus.modules.evidence.events import (
    EvidenceVersionCreated,
    EvidenceVersionWithdrawn,
    InboxFileAdded,
    InboxFileExtracted,
    UploadChecksRecorded,
)
from abacus.modules.evidence.export_activities import ACTIVITIES as EXPORT_ACTIVITIES
from abacus.modules.evidence.export_activities import SUBSCRIPTIONS as EXPORT_SUBSCRIPTIONS
from abacus.modules.evidence.export_activities import WORKFLOWS as EXPORT_WORKFLOWS
from abacus.modules.evidence.export_contract import exports_router, work_item_exports_router
from abacus.modules.evidence.export_currency import (
    ExportStale,
    FinalExport,
    FinalExportRequired,
    final_export_for_archive,
)
from abacus.modules.evidence.export_lifecycle import ACTIVITIES as EXPIRY_ACTIVITIES
from abacus.modules.evidence.export_lifecycle import SCHEDULES as EXPIRY_SCHEDULES
from abacus.modules.evidence.export_lifecycle import SUBSCRIPTIONS as EXPORT_CLOSE_SUBSCRIPTIONS
from abacus.modules.evidence.export_lifecycle import WORKFLOWS as EXPIRY_WORKFLOWS
from abacus.modules.evidence.export_lifecycle import (
    on_version_withdrawn as void_exports_on_withdrawal,
)
from abacus.modules.evidence.export_manifest import (
    FORMAT_VERSION as EXPORT_FORMAT_VERSION,
)
from abacus.modules.evidence.export_manifest import SCHEMA_FILE as EXPORT_SCHEMA_FILE
from abacus.modules.evidence.export_manifest import EngagementExportManifest
from abacus.modules.evidence.export_manifest import (
    manifest_json_schema as export_manifest_json_schema,
)
from abacus.modules.evidence.export_package import (
    SectionFile,
    SectionProvider,
    SectionRequest,
    register_export_section,
)
from abacus.modules.evidence.export_sections import (
    included_versions as included_export_versions,
)
from abacus.modules.evidence.export_sections import (
    register_export_audit_trail,
)
from abacus.modules.evidence.export_sections import (
    requester as export_requester,
)
from abacus.modules.evidence.export_sections import (
    section_csv as export_section_csv,
)
from abacus.modules.evidence.files_contract import files_router
from abacus.modules.evidence.firm_export_activities import ACTIVITIES as FIRM_EXPORT_ACTIVITIES
from abacus.modules.evidence.firm_export_activities import (
    SUBSCRIPTIONS as FIRM_EXPORT_SUBSCRIPTIONS,
)
from abacus.modules.evidence.firm_export_activities import WORKFLOWS as FIRM_EXPORT_WORKFLOWS
from abacus.modules.evidence.firm_export_contract import router as firm_export_router
from abacus.modules.evidence.firm_export_schedule import ACTIVITIES as SCHEDULE_ACTIVITIES
from abacus.modules.evidence.firm_export_schedule import SUBSCRIPTIONS as SCHEDULE_SUBSCRIPTIONS
from abacus.modules.evidence.firm_export_schedule import WORKFLOWS as SCHEDULE_WORKFLOWS
from abacus.modules.evidence.firm_export_schedule import register_firm_export_starter
from abacus.modules.evidence.firm_export_schedule_contract import (
    schedule_router as firm_export_schedule_router,
)
from abacus.modules.evidence.gate_facts import (
    decided_among,
    effective_decisions,
    review_assignees,
    waiting_among,
)
from abacus.modules.evidence.hold_activities import ACTIVITIES as HOLD_ACTIVITIES
from abacus.modules.evidence.hold_routes import router as legal_hold_router
from abacus.modules.evidence.hold_runs import SUBSCRIPTIONS as HOLD_SUBSCRIPTIONS
from abacus.modules.evidence.hold_runs import WORKFLOWS as HOLD_WORKFLOWS
from abacus.modules.evidence.hold_runs import with_hold_inheritance
from abacus.modules.evidence.holds import (
    HoldScope,
    HoldView,
    holds_covering,
    list_holds,
    place_hold,
)
from abacus.modules.evidence.holds import activate as legal_hold_activate
from abacus.modules.evidence.holds import apply_batch as legal_hold_apply_batch
from abacus.modules.evidence.inbox import add_to_inbox, register_match_picks
from abacus.modules.evidence.inbox import assign as assign_inbox_file
from abacus.modules.evidence.intake_filing import (
    Filed,
    IntakeObject,
    SupersedeMismatch,
    file_intake_object,
)
from abacus.modules.evidence.intake_keys import (
    destroy_intake_key,
    held_intake_objects,
    live_intake_keys,
    record_intake_key,
    screen_and_stage_detached,
)
from abacus.modules.evidence.intake_sources import IntakeSource, register_intake_source
from abacus.modules.evidence.item_detail import Download as DocumentDownload
from abacus.modules.evidence.item_detail import latest_document
from abacus.modules.evidence.masked_previews import intake_masked_pages, masked_preview_upload
from abacus.modules.evidence.masked_text import intake_masked_text
from abacus.modules.evidence.match_material import (
    Candidate,
    MatchMaterial,
    match_material,
    worth_matching,
)
from abacus.modules.evidence.matching import MIN_SCORE as SUGGESTION_MIN_SCORE
from abacus.modules.evidence.matching import suggest as suggest_by_name
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.pii_facts import tin_exposure
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
from abacus.modules.evidence.processing import workflow_id as upload_workflow_id
from abacus.modules.evidence.records import (
    RecordClass,
    StoredRecord,
    anchor_chain,
    get_record,
    put_record,
)
from abacus.modules.evidence.render import (
    CODE_COLUMN,
    CREDIT_COLUMN,
    DEBIT_COLUMN,
    FIRST_LINE_ROW,
    NAME_COLUMN,
    TOTAL_LABEL,
    LayerExport,
    LayerLine,
    TrialBalance,
    TrialBalanceLine,
    render_trial_balance,
    render_trial_balance_layers,
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
from abacus.modules.evidence.retention import (
    RECORD_TYPES,
    EffectivePolicy,
    PolicyChange,
    effective_policies,
    extend_retention_for,
    retain_until_for,
    set_policy,
)
from abacus.modules.evidence.retention_routes import platform_router as retention_platform_router
from abacus.modules.evidence.retention_routes import router as retention_router
from abacus.modules.evidence.retrieved_copies import (
    SOURCE_DOCUMENTS,
    file_retrieved_copy,
    pdf_text,
)
from abacus.modules.evidence.routes import firm_router, router

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.evidence.screening_facts import (
    ScreeningFacts,
    citation_sources,
    screening_facts,
    supported_citations,
    verified_citation_ids,
)
from abacus.modules.evidence.service import (
    EngagementArchived,
    EvidenceVersionRef,
    EvidenceVersionSummary,
    EvidenceVersionView,
    NewItem,
    Proposal,
    ProposalChanged,
    Provenance,
    ScreeningDecision,
    StoredObject,
    UndoneView,
    UndoWindowClosed,
    add_version,
    decide,
    decisions_on_screenings,
    engagement_snapshots,
    evidence_versions_for,
    read_content,
    read_version,
    register_proposal_source,
    release_member_assignments,
    return_files,
    review_decision_engagement,
    stage_content,
    undo_returned_files,
    undo_review_decision,
    version_content,
    version_view,
)
from abacus.modules.evidence.signed_copies import (
    SIGNED_AUTHORIZATIONS,
    ScreenedFile,
    file_signed_copy,
    read_staged,
    screen_and_stage,
    version_titles,
)
from abacus.modules.evidence.storage import (
    MAX_CONTENT_BYTES,
    ContentTooLarge,
    IntegrityError,
    check_ready,
    configure_storage,
)
from abacus.modules.evidence.trust_contract import router as trust_router
from abacus.modules.evidence.upload_facts import upload_facts
from abacus.modules.evidence.uploads import (
    UPLOAD_EDGE_BYTES,
    UPLOAD_ROUTE_PATHS,
    upload,
    upload_preview,
)
from abacus.modules.evidence.viewer import readable_version, signer_page, viewer_page
from abacus.modules.evidence.withdrawals import ACTIVITIES as WITHDRAWAL_ACTIVITIES
from abacus.modules.evidence.withdrawals import SUBSCRIPTIONS as WITHDRAWAL_SUBSCRIPTIONS
from abacus.modules.evidence.withdrawals import WORKFLOWS as WITHDRAWAL_WORKFLOWS
from abacus.modules.evidence.withdrawals import is_version_withdrawn, withdrawn_among
from abacus.modules.evidence.words import WORDS_VERSION, start_trust_layer_backfill, words_upload
from abacus.modules.evidence.workflow_types import INBOX as UPLOAD_INBOX
from abacus.modules.evidence.workflow_types import (
    INTAKE,
    BackfillInput,
    EngagementExportInput,
    ExportPackageFacts,
    FirmExportFacts,
    FirmExportInput,
    LegalHoldInput,
    UploadInput,
    WithdrawalPurgeInput,
)
from abacus.modules.evidence.workflow_types import VERSION as UPLOAD_VERSION
from abacus.modules.evidence.workflow_types import ExportFailure as ExportBuildFailure
from abacus.modules.evidence.workflows import (
    ANCHOR_ID,
    EXPORT_EXPIRY_ID,
    AuditAnchorWorkflow,
    EngagementExportWorkflow,
    EvidenceWithdrawalPurge,
    ExportExpirySweepWorkflow,
    FirmExportScheduleWorkflow,
    FirmExportWorkflow,
    LegalHoldApply,
    LegalHoldRelease,
    TrustLayerBackfill,
    UploadProcessing,
    firm_export_schedule_id,
)
from abacus.modules.identity.api import AbacusRouter, register_member_removed
from abacus.modules.ledger.api import TrialBalanceVersionCreated
from abacus.modules.platform.api import (
    register_audit_value_resolver,
    register_wisp_document_reader,
)
from abacus.modules.requests.api import register_upload_facts

ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    files_router,  # Files browser v1 stub (N-01-T02; ADR-158)
    withdrawal_router,  # C5 v1 stub (P-06-T01; ADR-162)
    duplicates_router,  # T-02-T17: a person resolves a flagged duplicate upload
    drops_router,  # C5 portal-pbc stub (R-01-T01): a portal drop
    void_router,  # C5 portal-pbc (TASK-1248): a person voids a wrong rule link
    trust_router,  # C4 v1 stub (P-03-T02; ADR-144)
    retention_router,  # Q-02-T23: a firm's retention policies
    retention_platform_router,  # Q-02-T23: staff floor and default sets
    legal_hold_router,  # Q-02-T29: legal holds
    # G-02-T11 (security-center v1; G-02-T19 live): before Q-02's router, whose
    # `POST /{export_id}/approve` would otherwise take `schedule/approve`.
    firm_export_schedule_router,
    firm_export_router,  # Q-02-T38 contract, live since Q-02-T43
    work_item_exports_router,  # A-01-T17 stub; A-01-T18 create, undo, reads (T22: download)
    exports_router,  # A-01-T17
)

# Q-02-T29: the legal-hold workflows and their activities beside upload processing; a new version
# gets its S3 holds before its processing starts. Importing `holds` registered `holds_covering`
# as the kernel's hold check (fail closed without it).
# P-06-T19 (ADR-162 §7): the withdrawal purge, started by `evidence_version.withdrawn`.
# A-01-T19: the engagement export, started by `engagement_export.requested`.
# Q-02-T21: the daily audit-chain anchor to the records bucket, on its Schedule.
WORKFLOWS: dict[type, str] = {
    **UPLOAD_WORKFLOWS,
    **HOLD_WORKFLOWS,
    **WITHDRAWAL_WORKFLOWS,
    **ANCHOR_WORKFLOWS,
    **EXPORT_WORKFLOWS,
    **EXPIRY_WORKFLOWS,  # A-01-T22: the daily export expiry sweep
    **SCHEDULE_WORKFLOWS,  # G-02-T19: the firm export's monthly run, on the firm's Schedule
    **FIRM_EXPORT_WORKFLOWS,  # Q-02-T43: the firm export, started by `firm_export.approved`
}
ACTIVITIES: tuple[object, ...] = (
    *UPLOAD_ACTIVITIES,
    *HOLD_ACTIVITIES,
    *WITHDRAWAL_ACTIVITIES,
    *ANCHOR_ACTIVITIES,
    *EXPORT_ACTIVITIES,
    *EXPIRY_ACTIVITIES,  # A-01-T22
    *SCHEDULE_ACTIVITIES,  # G-02-T19
    *FIRM_EXPORT_ACTIVITIES,  # Q-02-T43
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
    **EXPORT_SUBSCRIPTIONS,
    **EXPORT_CLOSE_SUBSCRIPTIONS,  # A-01-T22: an expired or voided export's segments go
    **SCHEDULE_SUBSCRIPTIONS,  # G-02-T19: converge the firm's export Schedule on its record
    **FIRM_EXPORT_SUBSCRIPTIONS,  # Q-02-T43: the build starts; an expired archive's segments go
}
# P-03-T12: the moved and broken detector follows each (both idempotent; a failure retries both).
SUBSCRIPTIONS = {
    **_SUBSCRIPTIONS,
    EvidenceVersionCreated.event_type: in_turn(
        _SUBSCRIPTIONS[EvidenceVersionCreated.event_type], on_version_created
    ),
    # A-02-T22: a trial balance re-version moves citations to the snapshot it replaced.
    TrialBalanceVersionCreated.event_type: on_trial_balance_version_created,
    # A-01-T22 (P-31): a withdrawn version voids every ready export holding it.
    # First, so a later subscriber's failure never holds the void back.
    EvidenceVersionWithdrawn.event_type: in_turn(
        void_exports_on_withdrawal,
        in_turn(_SUBSCRIPTIONS[EvidenceVersionWithdrawn.event_type], on_version_withdrawn),
    ),
}
SCHEDULES = (*ANCHOR_SCHEDULES, *EXPIRY_SCHEDULES)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# G-02-T09 gap (DEC-459): ADM-07's values for versions and PII reveals (masked).
register_audit_value_resolver("evidence_version", evidence_version_values)
register_audit_value_resolver("pii_reveal", pii_reveal_values)
# A-01-T10 (C5 v1.1, DEC-313): a request row's latest upload and the matcher's confidence.
register_upload_facts(upload_facts)

__all__ = [
    "ACTIVITIES",
    "ANCHOR_ID",
    "CODE_COLUMN",
    "CONTENT_READ_KIND",
    "CREDIT_COLUMN",
    "DEBIT_COLUMN",
    "EXPORT_EXPIRY_ID",
    "EXPORT_FORMAT_VERSION",
    "EXPORT_SCHEMA_FILE",
    "FIRST_LINE_ROW",
    "INTAKE",
    "MAX_CONTENT_BYTES",
    "NAME_COLUMN",
    "RECORD_TYPES",
    "ROUTERS",
    "SCHEDULES",
    "SIGNED_AUTHORIZATIONS",
    "SOURCE_DOCUMENTS",
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
    "AuditAnchorWorkflow",
    "BackfillInput",
    "Candidate",
    "CitationAnchor",
    "CitationClaim",
    "CitationKind",
    "CitationLabel",
    "CitationVerdict",
    "ClassifiedIntake",
    "ContentTooLarge",
    "DocumentDownload",  # G-02-T20: the WISP pack's documents
    "EffectivePolicy",
    "EngagementArchived",
    "EngagementExportInput",
    "EngagementExportManifest",
    "EngagementExportWorkflow",
    "EvidenceVersionCreated",
    "EvidenceVersionRef",
    "EvidenceVersionSummary",
    "EvidenceVersionView",
    "EvidenceVersionWithdrawn",
    "EvidenceWithdrawalPurge",
    "ExportBuildFailure",
    "ExportExpirySweepWorkflow",
    "ExportPackageFacts",
    "ExportStale",
    "Filed",
    "FinalExport",
    "FinalExportRequired",
    "FirmExportFacts",
    "FirmExportInput",
    "FirmExportScheduleWorkflow",
    "FirmExportWorkflow",
    "GlBalanceRow",
    "GlHeader",
    "GlRenderEntry",
    "HoldScope",
    "HoldView",
    "InboxFileAdded",
    "InboxFileExtracted",
    "IntakeObject",
    "IntakeSource",
    "IntegrityError",
    "LayerExport",
    "LayerLine",
    "LegalHoldApply",
    "LegalHoldInput",
    "LegalHoldRelease",
    "MatchMaterial",
    "NewItem",
    "PolicyChange",
    "PortalFile",
    "Proposal",
    "ProposalChanged",
    "Provenance",
    "RecordClass",
    "RecordedCitation",
    "ReviewMaterial",
    "ScreenedFile",
    "ScreeningDecision",
    "ScreeningFacts",
    "SectionFile",
    "SectionProvider",
    "SectionRequest",
    "SentBack",
    "StoredObject",
    "StoredRecord",
    "SupersedeMismatch",
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
    "assign_inbox_file",
    "check_ready",
    "check_upload_content",
    "citation_cell_reason",
    "citation_cell_text",
    "citation_display",
    "citation_sources",
    "classifier_rules",
    "classify_intake",
    "client_pre_checks",
    "column_letters",
    "configure_storage",
    "decide",
    "decided_among",
    "decisions_on_screenings",
    "destroy_intake_key",
    "drop_batch",
    "effective_decisions",
    "effective_policies",
    "engagement_snapshots",
    "evidence_versions_for",
    "export_manifest_json_schema",
    "export_requester",
    "export_section_csv",
    "extend_retention_for",
    "file_intake_object",
    "file_retrieved_copy",
    "file_signed_copy",
    "filed_classification_match",
    "final_export_for_archive",
    "firm_export_schedule_id",
    "firm_router",
    "get_record",
    "held_intake_objects",
    "holds_covering",
    "included_export_versions",
    "intake_masked_pages",
    "intake_masked_text",
    "is_version_withdrawn",
    "latest_document",
    "legal_hold_activate",
    "legal_hold_apply_batch",
    "list_holds",
    "live_intake_keys",
    "mark_sources_superseded",
    "masked_preview_upload",
    "match_material",
    "normalised_text",
    "page_quote_reason",
    "pdf_text",
    "pii_scan_upload",
    "place_hold",
    "portal_files",
    "process_upload",
    "put_record",
    "quote_in",
    "read_content",
    "read_staged",
    "read_version",
    "record_agent_classification",
    "record_citations",
    "record_intake_key",
    "register_citable",
    "register_export_audit_trail",
    "register_export_section",
    "register_firm_export_starter",
    "register_intake_source",
    "register_match_picks",
    "register_proposal_source",
    "render_general_ledger",
    "render_journal_listing",
    "render_trial_balance",
    "render_trial_balance_layers",
    "retain_until_for",
    "return_files",
    "review_assignees",
    "review_decision_engagement",
    "review_material",
    "router",
    "screen_and_stage",
    "screen_and_stage_detached",
    "screening_facts",
    "set_policy",
    "signer_page",
    "stage_content",
    "stale_pdfs",
    "start_trust_layer_backfill",
    "suggest_by_name",
    "supported_citations",
    "tin_exposure",
    "undo_returned_files",
    "undo_review_decision",
    "upload",
    "upload_preview",
    "upload_workflow_id",
    "verified_citation_ids",
    "version_content",
    "version_titles",
    "version_view",
    "version_with_fingerprint",
    "viewer_page",
    "waiting_among",
    "withdrawn_among",
    "words_upload",
    "worth_matching",
]

# SPEC-017 (TASK-032 D2): a removed team member's review assignments go back to the queue.
register_member_removed(release_member_assignments)
# P-07-T36 review (DEC-375): a screening record's evidence link must be a file the person reads.
register_evidence_readable(readable_version)
# G-02-T20: the WISP pack reads each document through the item download, as its requester.
register_wisp_document_reader(latest_document)
