"""Public interface of the evidence module; other modules import only this (ADR-008)."""

from abacus.modules.evidence.activities import ACTIVITIES
from abacus.modules.evidence.events import EvidenceVersionCreated, InboxFileAdded
from abacus.modules.evidence.processing import SUBSCRIPTIONS, WORKFLOWS
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
    "TOTAL_LABEL",
    "UPLOAD_VERSION",
    "WORKFLOWS",
    "XLSX_MEDIA_TYPE",
    "ContentTooLarge",
    "EngagementArchived",
    "EvidenceVersionCreated",
    "EvidenceVersionRef",
    "EvidenceVersionSummary",
    "EvidenceVersionView",
    "InboxFileAdded",
    "IntegrityError",
    "NewItem",
    "Proposal",
    "Provenance",
    "StoredObject",
    "TrialBalance",
    "TrialBalanceLine",
    "UploadInput",
    "UploadProcessing",
    "add_version",
    "check_ready",
    "engagement_snapshots",
    "evidence_versions_for",
    "read_content",
    "read_version",
    "register_proposal_source",
    "render_trial_balance",
    "router",
    "stage_content",
    "version_view",
]

# SPEC-017 (TASK-032 D2): a removed team member's review assignments go back to the queue.
register_member_removed(release_member_assignments)
