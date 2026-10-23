"""Public interface of the evidence module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.evidence.activities import ACTIVITIES
from abacus.modules.evidence.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.evidence.contract import withdrawal_router
from abacus.modules.evidence.events import (
    EvidenceVersionCreated,
    InboxFileAdded,
    InboxFileExtracted,
    UploadChecksRecorded,
)
from abacus.modules.evidence.inbox import add_to_inbox, register_match_picks
from abacus.modules.evidence.match_material import (
    Candidate,
    MatchMaterial,
    match_material,
    worth_matching,
)
from abacus.modules.evidence.matching import MIN_SCORE as SUGGESTION_MIN_SCORE
from abacus.modules.evidence.matching import suggest as suggest_by_name
from abacus.modules.evidence.processing import (
    SUBSCRIPTIONS,
    WORKFLOWS,
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

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.evidence.retention_routes import platform_router as retention_platform_router
from abacus.modules.evidence.retention_routes import router as retention_router
from abacus.modules.evidence.routes import firm_router, router
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
    add_version,
    decisions_on_screenings,
    engagement_snapshots,
    evidence_versions_for,
    read_content,
    read_version,
    register_proposal_source,
    release_member_assignments,
    stage_content,
    version_view,
)
from abacus.modules.evidence.storage import (
    MAX_CONTENT_BYTES,
    ContentTooLarge,
    IntegrityError,
    check_ready,
)
from abacus.modules.evidence.trust_contract import router as trust_router
from abacus.modules.evidence.uploads import upload
from abacus.modules.evidence.workflow_types import INBOX as UPLOAD_INBOX
from abacus.modules.evidence.workflow_types import VERSION as UPLOAD_VERSION
from abacus.modules.evidence.workflow_types import UploadInput
from abacus.modules.evidence.workflows import UploadProcessing
from abacus.modules.identity.api import AbacusRouter, register_member_removed

ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    withdrawal_router,  # C5 v1 stub (P-06-T01; ADR-162)
    trust_router,  # C4 v1 stub (P-03-T02; ADR-144)
    retention_router,  # Q-02-T23: a firm's retention policies
    retention_platform_router,  # Q-02-T23: staff floor and default sets
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

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
    "UPLOAD_INBOX",
    "UPLOAD_VERSION",
    "WORKFLOWS",
    "XLSX_MEDIA_TYPE",
    "Candidate",
    "ContentTooLarge",
    "EngagementArchived",
    "EvidenceVersionCreated",
    "EvidenceVersionRef",
    "EvidenceVersionSummary",
    "EvidenceVersionView",
    "GlBalanceRow",
    "GlHeader",
    "GlRenderEntry",
    "InboxFileAdded",
    "InboxFileExtracted",
    "IntegrityError",
    "MatchMaterial",
    "NewItem",
    "Proposal",
    "Provenance",
    "RecordClass",
    "ReviewMaterial",
    "ScreeningDecision",
    "StoredObject",
    "StoredRecord",
    "TrialBalance",
    "TrialBalanceLine",
    "UploadChecksRecorded",
    "UploadInput",
    "UploadProcessing",
    "add_to_inbox",
    "add_version",
    "anchor_chain",
    "check_ready",
    "check_upload_content",
    "decisions_on_screenings",
    "engagement_snapshots",
    "evidence_versions_for",
    "extend_retention_for",
    "firm_router",
    "match_material",
    "process_upload",
    "put_record",
    "read_content",
    "read_version",
    "register_match_picks",
    "register_proposal_source",
    "render_general_ledger",
    "render_journal_listing",
    "render_trial_balance",
    "retain_until_for",
    "review_material",
    "router",
    "stage_content",
    "stale_pdfs",
    "suggest_by_name",
    "upload",
    "version_view",
    "worth_matching",
]

# SPEC-017 (TASK-032 D2): a removed team member's review assignments go back to the queue.
register_member_removed(release_member_assignments)
