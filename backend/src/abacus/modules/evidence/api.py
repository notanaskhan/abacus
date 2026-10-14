"""Public interface of the evidence module; other modules import only this (ADR-008)."""

from abacus.modules.evidence.activities import ACTIVITIES
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
)
from abacus.modules.evidence.processing import check_upload as check_upload_content
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
from abacus.modules.evidence.routes import router
from abacus.modules.evidence.service import (
    EngagementArchived,
    EvidenceVersionRef,
    EvidenceVersionSummary,
    EvidenceVersionView,
    NewItem,
    Proposal,
    Provenance,
    StoredObject,
    add_version,
    engagement_snapshots,
    evidence_versions_for,
    read_content,
    read_version,
    register_proposal_source,
    release_member_assignments,
    stage_content,
    version_view,
)
from abacus.modules.evidence.storage import ContentTooLarge, IntegrityError, check_ready
from abacus.modules.evidence.uploads import upload
from abacus.modules.evidence.workflow_types import INBOX as UPLOAD_INBOX
from abacus.modules.evidence.workflow_types import VERSION as UPLOAD_VERSION
from abacus.modules.evidence.workflow_types import UploadInput
from abacus.modules.evidence.workflows import UploadProcessing
from abacus.modules.identity.api import register_member_removed

__all__ = [
    "ACTIVITIES",
    "CODE_COLUMN",
    "CREDIT_COLUMN",
    "DEBIT_COLUMN",
    "FIRST_LINE_ROW",
    "NAME_COLUMN",
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
    "InboxFileAdded",
    "InboxFileExtracted",
    "IntegrityError",
    "MatchMaterial",
    "NewItem",
    "Proposal",
    "Provenance",
    "ReviewMaterial",
    "StoredObject",
    "TrialBalance",
    "TrialBalanceLine",
    "UploadChecksRecorded",
    "UploadInput",
    "UploadProcessing",
    "add_to_inbox",
    "add_version",
    "check_ready",
    "check_upload_content",
    "engagement_snapshots",
    "evidence_versions_for",
    "match_material",
    "process_upload",
    "read_content",
    "read_version",
    "register_match_picks",
    "register_proposal_source",
    "render_trial_balance",
    "review_material",
    "router",
    "stage_content",
    "suggest_by_name",
    "upload",
    "version_view",
    "worth_matching",
]

# SPEC-017 (TASK-032 D2): a removed team member's review assignments go back to the queue.
register_member_removed(release_member_assignments)
