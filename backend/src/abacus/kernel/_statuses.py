"""GENERATED from docs/product/status-vocabulary.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.status_vocabulary
"""

from enum import StrEnum

# fmt: off


class EngagementStatus(StrEnum):
    PROSPECT = "prospect"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CONTRACTED = "contracted"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    DELIVERED = "delivered"
    ARCHIVED = "archived"


class ReturnStatus(StrEnum):
    NOT_STARTED = "not_started"
    GATHERING = "gathering"
    PREPARING = "preparing"
    PREPARED = "prepared"
    IN_REVIEW = "in_review"
    ACTION_REQUIRED = "action_required"
    APPROVED = "approved"
    AWAITING_SIGNATURE = "awaiting_signature"
    FILED = "filed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FIXING = "fixing"


class ReturnFlagStatus(StrEnum):
    EXTENDED = "extended"
    ON_HOLD = "on_hold"
    SUPERSEDED = "superseded"
    AMENDED = "amended"


class ReturnSyncChipStatus(StrEnum):
    NOT_YET_EXPORTED = "not_yet_exported"
    READY_FOR_EXPORT = "ready_for_export"
    EXPORTING = "exporting"
    SYNCED = "synced"
    OUT_OF_SYNC = "out_of_sync"
    IMPORT_PENDING_APPROVAL = "import_pending_approval"
    FAILED = "failed"


class K1PackageStatus(StrEnum):
    NOT_PREPARED = "not_prepared"
    DRAFT = "draft"
    RELEASED = "released"
    VIEWED = "viewed"
    DOWNLOADED = "downloaded"
    BOUNCED = "bounced"
    SUPERSEDED = "superseded"


class AuditEngagementStatus(StrEnum):
    PLANNING = "planning"
    FIELDWORK = "fieldwork"
    IN_REVIEW = "in_review"
    COMPLETION = "completion"
    READY_TO_RELEASE = "ready_to_release"
    RELEASED = "released"
    ARCHIVING = "archiving"
    ARCHIVED = "archived"
    # derived, never stored: processing


class AuditSectionStatus(StrEnum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    WAITING_ON_INPUTS = "waiting_on_inputs"
    READY_TO_RUN = "ready_to_run"
    IN_PROGRESS = "in_progress"
    RUNNING = "running"
    BLOCKED_ON_DECISION = "blocked_on_decision"
    DRAFT_READY = "draft_ready"
    PREPARED = "prepared"
    REVIEWED = "reviewed"
    SIGNED_OFF = "signed_off"
    LOCKED = "locked"
    FAILED = "failed"
    CHANGED_AFTER_SIGNOFF = "changed_after_signoff"


class ProgramBoardStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETE = "complete"


class ControlBoardStatus(StrEnum):
    NOT_STARTED = "not_started"
    TESTING = "testing"
    PENDING = "pending"
    PREPARER_REVIEW = "preparer_review"
    MANAGER_REVIEW = "manager_review"
    REVIEW_COMPLETE = "review_complete"


class CardOverlayStatus(StrEnum):
    NEEDS_INPUT = "needs_input"
    WAITING_ON_CLIENT = "waiting_on_client"
    AGENT_RUNNING = "agent_running"
    SENT_BACK = "sent_back"


class ControlTestResultStatus(StrEnum):
    NOT_TESTED = "not_tested"
    NO_EXCEPTIONS_NOTED = "no_exceptions_noted"
    EXCEPTIONS_NOTED = "exceptions_noted"
    NOT_APPLICABLE = "not_applicable"


class AttestExceptionStatus(StrEnum):
    NOTED = "noted"
    RESPONSE_RECEIVED = "response_received"
    EVALUATED = "evaluated"


class DeficiencyStatus(StrEnum):
    EXCEPTION_FOR_RESOLUTION = "exception_for_resolution"
    PROPOSED = "proposed"
    CONCLUDED = "concluded"
    COMMUNICATED = "communicated"


class DeficiencySeverityStatus(StrEnum):
    DEFICIENCY = "deficiency"
    SIGNIFICANT_DEFICIENCY = "significant_deficiency"
    MATERIAL_WEAKNESS = "material_weakness"


class MisstatementStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    BELOW_CT = "below_ct"
    PROPOSED_TO_CLIENT = "proposed_to_client"
    BOOKED = "booked"
    PASSED_ON_SUM = "passed_on_sum"


class MisstatementTypeStatus(StrEnum):
    FACTUAL = "factual"
    JUDGMENTAL = "judgmental"
    PROJECTED = "projected"


class IaIssueRatingStatus(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionPlanStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    # derived, never stored: overdue


class CloseStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DELIVERED = "delivered"
    LOCKED = "locked"
    # derived, never stored: past_due


class CloseTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_ATTENTION = "needs_attention"
    DONE = "done"
    FAILED = "failed"


class ProposedEntryStatus(StrEnum):
    PROPOSED = "proposed"
    WITHIN_THRESHOLD = "within_threshold"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    CLIENT_APPROVED = "client_approved"
    POSTED = "posted"
    FAILED_POST = "failed_post"
    REVERSED = "reversed"


class TieOutTallyStatus(StrEnum):
    TIE = "tie"
    OFF = "off"
    CHECK = "check"
    PENDING = "pending"
    TIES_ONCE_POSTED = "ties_once_posted"
    RECONCILED = "reconciled"


class RequestStatus(StrEnum):
    DRAFT = "draft"
    REQUESTED = "requested"
    UPLOADED = "uploaded"
    RECEIVED = "received"
    RETURNED = "returned"
    NOT_APPLICABLE = "not_applicable"
    # derived, never stored: overdue


class RequestCloseStatus(StrEnum):
    REQUESTED = "requested"
    RECEIVED = "received"
    MATCHED = "matched"
    PENDING_INCORPORATION = "pending_incorporation"
    INCORPORATED = "incorporated"


class DocumentStatus(StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    MATCHED = "matched"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceScreeningStatus(StrEnum):
    PASSED = "passed"
    FLAGGED = "flagged"
    NOT_SCREENED = "not_screened"


class InboxItemStatus(StrEnum):
    NEW = "new"
    WAITING = "waiting"
    FILED = "filed"
    IGNORED = "ignored"


class IssueStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    REOPENED = "reopened"
    NOT_APPLICABLE = "not_applicable"


class IssueSeverityStatus(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueAuditRouteStatus(StrEnum):
    UNDER_EVALUATION = "under_evaluation"
    CONVERTED_TO_MISSTATEMENT = "converted_to_misstatement"
    CONVERTED_TO_DEFICIENCY = "converted_to_deficiency"


class ReviewNoteStatus(StrEnum):
    OPEN = "open"
    RESPONDED = "responded"
    CLEARED = "cleared"
    CLOSED = "closed"
    WITHDRAWN = "withdrawn"


class CommentThreadStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class TodoStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    # derived, never stored: overdue


class EnvelopeStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PARTIALLY_SIGNED = "partially_signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    VOIDED = "voided"


class NoticeStatus(StrEnum):
    RECEIVED = "received"
    CLASSIFIED = "classified"
    ANALYZING = "analyzing"
    RESPONSE_DRAFTED = "response_drafted"
    APPROVED = "approved"
    SENT = "sent"
    AWAITING_IRS = "awaiting_irs"
    CLOSED = "closed"
    ESCALATED = "escalated"


class ConsentStatus(StrEnum):
    REQUESTED = "requested"
    SIGNED = "signed"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    DECLINED = "declined"
    REVOKED = "revoked"


class ConsentPurposeStatus(StrEnum):
    USE = "use"
    AI_DISCLOSURE = "ai_disclosure"
    OFFSHORE_DISCLOSURE = "offshore_disclosure"
    THIRD_PARTY_DISCLOSURE = "third_party_disclosure"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    BLOCKED_ON_DECISION = "blocked_on_decision"
    WAITING_ON_INPUTS = "waiting_on_inputs"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # derived, never stored: approved, partially_approved, rejected


class WorkbenchSessionStatus(StrEnum):
    LIVE = "live"
    RUNNING = "running"
    AWAITING_ANSWER = "awaiting_answer"
    READY_FOR_REVIEW = "ready_for_review"
    COMPLETE = "complete"
    FAILED = "failed"


class IntegrationStatus(StrEnum):
    AVAILABLE = "available"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    NEEDS_ATTENTION = "needs_attention"
    NEEDS_REAUTH = "needs_reauth"
    DISCONNECTED = "disconnected"
    COMING_SOON = "coming_soon"
    PAUSED = "paused"


class AgentTemplateStatus(StrEnum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    COMING_SOON = "coming_soon"


class TemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class EngagementTemplateLinkStatus(StrEnum):
    CURRENT = "current"
    UPDATE_AVAILABLE = "update_available"
    UPDATED = "updated"
    HELD = "held"


class TriggerStatus(StrEnum):
    ON = "on"
    OFF = "off"
    DUPLICATE = "duplicate"


class SavedPromptAccessStatus(StrEnum):
    FIRM = "firm"
    SERVICE_LINE = "service_line"
    PERSONAL = "personal"


class LearnedContextItemStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RETIRED = "retired"


class BinderStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    COMPLETE = "complete"
    CLOSED = "closed"


class ArchiveStatus(StrEnum):
    ASSEMBLING = "assembling"
    LOCKED = "locked"
    POST_LOCK_ADDITION = "post_lock_addition"


class CheckpointStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    CURRENT = "current"


class ProjectStatus(StrEnum):
    SCOPING = "scoping"
    ACTIVE = "active"
    DELIVERED = "delivered"
    CLOSED = "closed"


class ConsolidationStatus(StrEnum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class EliminationEntryStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    POSTED = "posted"


class ComponentStatus(StrEnum):
    FULL_SCOPE = "full_scope"
    SPECIFIC_PROCEDURES = "specific_procedures"
    ANALYTICAL_ONLY = "analytical_only"


class ComponentInstructionsStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"


class ComponentDeliverableStatus(StrEnum):
    EXPECTED = "expected"
    RECEIVED = "received"
    REVIEWED = "reviewed"
    # derived, never stored: late


class LinkedValueStatus(StrEnum):
    TB_LINKED = "tb_linked"
    FORMULA = "formula"
    OVERRIDE = "override"
    STALE_OVERRIDE = "stale_override"


# Each object's stored codes, and their SQL CHECK list.
STORED: dict[str, tuple[str, ...]] = {
    "engagement": (
        "prospect",
        "accepted",
        "declined",
        "contracted",
        "active",
        "on_hold",
        "delivered",
        "archived",
    ),
    "return": (
        "not_started",
        "gathering",
        "preparing",
        "prepared",
        "in_review",
        "action_required",
        "approved",
        "awaiting_signature",
        "filed",
        "accepted",
        "rejected",
        "fixing",
    ),
    "return_flag": (
        "extended",
        "on_hold",
        "superseded",
        "amended",
    ),
    "return_sync_chip": (
        "not_yet_exported",
        "ready_for_export",
        "exporting",
        "synced",
        "out_of_sync",
        "import_pending_approval",
        "failed",
    ),
    "k1_package": (
        "not_prepared",
        "draft",
        "released",
        "viewed",
        "downloaded",
        "bounced",
        "superseded",
    ),
    "audit_engagement": (
        "planning",
        "fieldwork",
        "in_review",
        "completion",
        "ready_to_release",
        "released",
        "archiving",
        "archived",
    ),
    "audit_section": (
        "not_started",
        "queued",
        "waiting_on_inputs",
        "ready_to_run",
        "in_progress",
        "running",
        "blocked_on_decision",
        "draft_ready",
        "prepared",
        "reviewed",
        "signed_off",
        "locked",
        "failed",
        "changed_after_signoff",
    ),
    "program_board": (
        "not_started",
        "in_progress",
        "in_review",
        "complete",
    ),
    "control_board": (
        "not_started",
        "testing",
        "pending",
        "preparer_review",
        "manager_review",
        "review_complete",
    ),
    "card_overlay": (
        "needs_input",
        "waiting_on_client",
        "agent_running",
        "sent_back",
    ),
    "control_test_result": (
        "not_tested",
        "no_exceptions_noted",
        "exceptions_noted",
        "not_applicable",
    ),
    "attest_exception": (
        "noted",
        "response_received",
        "evaluated",
    ),
    "deficiency": (
        "exception_for_resolution",
        "proposed",
        "concluded",
        "communicated",
    ),
    "deficiency_severity": (
        "deficiency",
        "significant_deficiency",
        "material_weakness",
    ),
    "misstatement": (
        "candidate",
        "confirmed",
        "below_ct",
        "proposed_to_client",
        "booked",
        "passed_on_sum",
    ),
    "misstatement_type": (
        "factual",
        "judgmental",
        "projected",
    ),
    "ia_issue_rating": (
        "high",
        "medium",
        "low",
    ),
    "action_plan": (
        "open",
        "in_progress",
        "implemented",
        "validated",
    ),
    "close": (
        "not_started",
        "in_progress",
        "in_review",
        "approved",
        "delivered",
        "locked",
    ),
    "close_task": (
        "queued",
        "running",
        "needs_attention",
        "done",
        "failed",
    ),
    "proposed_entry": (
        "proposed",
        "within_threshold",
        "review_required",
        "approved",
        "client_approved",
        "posted",
        "failed_post",
        "reversed",
    ),
    "tie_out_tally": (
        "tie",
        "off",
        "check",
        "pending",
        "ties_once_posted",
        "reconciled",
    ),
    "request": (
        "draft",
        "requested",
        "uploaded",
        "received",
        "returned",
        "not_applicable",
    ),
    "request_close": (
        "requested",
        "received",
        "matched",
        "pending_incorporation",
        "incorporated",
    ),
    "document": (
        "uploading",
        "processing",
        "classified",
        "matched",
        "approved",
        "rejected",
        "superseded",
    ),
    "evidence_screening": (
        "passed",
        "flagged",
        "not_screened",
    ),
    "inbox_item": (
        "new",
        "waiting",
        "filed",
        "ignored",
    ),
    "issue": (
        "open",
        "in_progress",
        "resolved",
        "verified",
        "reopened",
        "not_applicable",
    ),
    "issue_severity": (
        "high",
        "medium",
        "low",
    ),
    "issue_audit_route": (
        "under_evaluation",
        "converted_to_misstatement",
        "converted_to_deficiency",
    ),
    "review_note": (
        "open",
        "responded",
        "cleared",
        "closed",
        "withdrawn",
    ),
    "comment_thread": (
        "open",
        "resolved",
    ),
    "todo": (
        "open",
        "done",
    ),
    "envelope": (
        "draft",
        "sent",
        "viewed",
        "partially_signed",
        "completed",
        "declined",
        "expired",
        "voided",
    ),
    "notice": (
        "received",
        "classified",
        "analyzing",
        "response_drafted",
        "approved",
        "sent",
        "awaiting_irs",
        "closed",
        "escalated",
    ),
    "consent": (
        "requested",
        "signed",
        "expiring",
        "expired",
        "declined",
        "revoked",
    ),
    "consent_purpose": (
        "use",
        "ai_disclosure",
        "offshore_disclosure",
        "third_party_disclosure",
    ),
    "agent_run": (
        "queued",
        "planning",
        "awaiting_plan_approval",
        "dispatched",
        "running",
        "needs_input",
        "blocked_on_decision",
        "waiting_on_inputs",
        "succeeded",
        "failed",
        "cancelled",
    ),
    "workbench_session": (
        "live",
        "running",
        "awaiting_answer",
        "ready_for_review",
        "complete",
        "failed",
    ),
    "integration": (
        "available",
        "connecting",
        "connected",
        "needs_attention",
        "needs_reauth",
        "disconnected",
        "coming_soon",
        "paused",
    ),
    "agent_template": (
        "available",
        "installed",
        "update_available",
        "coming_soon",
    ),
    "template_version": (
        "draft",
        "published",
        "deprecated",
    ),
    "engagement_template_link": (
        "current",
        "update_available",
        "updated",
        "held",
    ),
    "trigger": (
        "on",
        "off",
        "duplicate",
    ),
    "saved_prompt_access": (
        "firm",
        "service_line",
        "personal",
    ),
    "learned_context_item": (
        "proposed",
        "approved",
        "retired",
    ),
    "binder": (
        "draft",
        "published",
        "unpublished",
        "complete",
        "closed",
    ),
    "archive": (
        "assembling",
        "locked",
        "post_lock_addition",
    ),
    "checkpoint": (
        "proposed",
        "approved",
        "rejected",
        "current",
    ),
    "project": (
        "scoping",
        "active",
        "delivered",
        "closed",
    ),
    "consolidation": (
        "draft",
        "finalized",
    ),
    "elimination_entry": (
        "proposed",
        "approved",
        "posted",
    ),
    "component": (
        "full_scope",
        "specific_procedures",
        "analytical_only",
    ),
    "component_instructions": (
        "draft",
        "sent",
        "acknowledged",
    ),
    "component_deliverable": (
        "expected",
        "received",
        "reviewed",
    ),
    "linked_value": (
        "tb_linked",
        "formula",
        "override",
        "stale_override",
    ),
}
CHECKS: dict[str, str] = {
    name: "(" + ", ".join(f"'{code}'" for code in codes) + ")"
    for name, codes in STORED.items()
}
