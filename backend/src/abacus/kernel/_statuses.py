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


class EngineImportStatus(StrEnum):
    SCANNING = "scanning"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROUTED = "routed"


class K3Status(StrEnum):
    INCLUDED = "included"
    NOT_REQUIRED = "not_required"
    NOT_INCLUDED = "not_included"


class TranscriptParseStatus(StrEnum):
    QUEUED = "queued"
    PARSED = "parsed"
    FAILED = "failed"


class K1PackageStatus(StrEnum):
    NOT_PREPARED = "not_prepared"
    DRAFT = "draft"
    RELEASED = "released"
    VIEWED = "viewed"
    DOWNLOADED = "downloaded"
    BOUNCED = "bounced"
    SUPERSEDED = "superseded"


class QuestionnaireStatus(StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    SUBMITTED = "submitted"


class RecipientDetailsChangeStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class K1HandoffStatus(StrEnum):
    AWAITING = "awaiting"
    RECEIVED = "received"


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


class EngagementExportStatus(StrEnum):
    QUEUED = "queued"
    PACKAGING = "packaging"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"
    UNDONE = "undone"


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


class TrialBalanceLabelStatus(StrEnum):
    STANDARD = "standard"
    INTERIM = "interim"
    PRIOR = "prior"
    BUDGET = "budget"
    PRELIMINARY = "preliminary"


class TrialBalanceLayerStatus(StrEnum):
    UNADJUSTED = "unadjusted"
    AJE = "aje"
    RJE = "rje"
    FINAL = "final"


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
    HELD = "held"
    WITHDRAWN = "withdrawn"


class InboxThreadStatus(StrEnum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    IGNORED = "ignored"


class PortalIntakeUploadStatus(StrEnum):
    SENT = "sent"
    RECEIVED = "received"
    WITHDRAWN = "withdrawn"


class FileDocumentStatus(StrEnum):
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    ON_HOLD = "on_hold"


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


class SignOffSlotStatus(StrEnum):
    pass
    # derived, never stored: signed, stale


class HumanGateStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    VOIDED = "voided"
    # derived, never stored: snoozed


class DueRiskStatus(StrEnum):
    pass
    # derived, never stored: overdue, due_soon, approaching, later


class DecisionCardStatus(StrEnum):
    AWAITING_ROLE = "awaiting_role"
    DECIDED = "decided"
    SUPERSEDED = "superseded"


class FieldValueStatus(StrEnum):
    pass
    # derived, never stored: updated, edited, estimate, unsupported


class CommentThreadStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class TodoStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    # derived, never stored: overdue


class MethodologyVersionStatus(StrEnum):
    DRAFT = "draft"
    PARSING = "parsing"
    NEEDS_REVIEW = "needs_review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    DISCARDED = "discarded"


class MethodologyImportStatus(StrEnum):
    AWAITING_FILES = "awaiting_files"
    SCANNING = "scanning"
    PARSING = "parsing"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


class KnowledgeItemStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class TaxAuthorizationStatus(StrEnum):
    REQUESTED = "requested"
    ON_FILE = "on_file"
    EXPIRED = "expired"
    REVOKED = "revoked"
    # derived, never stored: not_on_file


class EfileAckStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class FirmStandardVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISCARDED = "discarded"
    # derived, never stored: superseded


class ReferenceSetVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"
    # derived, never stored: superseded


class ParseFlagStatus(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    SPLIT_ACROSS_PAGES = "split_across_pages"
    NUMBERING_GAP = "numbering_gap"
    UNVERIFIED_CITATION = "unverified_citation"
    CROSS_REFERENCE_MISSING = "cross_reference_missing"


class EnvelopeStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PARTIALLY_SIGNED = "partially_signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    VOIDED = "voided"


class EnvelopeSignerStatus(StrEnum):
    PENDING = "pending"
    VIEWED = "viewed"
    VERIFIED = "verified"
    SIGNED = "signed"
    DECLINED = "declined"
    VERIFICATION_FAILED = "verification_failed"


class SigningStepStatus(StrEnum):
    pass
    # derived, never stored: verify, review, sign, done


class EnvelopePurposeStatus(StrEnum):
    E_FILE_AUTHORIZATION = "e_file_authorization"
    ENGAGEMENT_LETTER = "engagement_letter"
    REPRESENTATION_LETTER = "representation_letter"
    CONSENT_7216 = "consent_7216"


class GeneratedDocumentStatus(StrEnum):
    DRAFTING = "drafting"
    DRAFT = "draft"
    APPROVED = "approved"
    LOCKED = "locked"


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
    SUPERSEDED = "superseded"
    # derived, never stored: not_requested


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


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ADOPTED = "adopted"
    EDITED = "edited"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_EDITS = "approved_with_edits"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


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
    SAVED = "saved"
    # derived, never stored: current


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


class ClientStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FORMER = "former"


class InvitationStatus(StrEnum):
    NOT_INVITED = "not_invited"
    INVITED = "invited"
    ACTIVE = "active"
    LOCKED = "locked"
    DEACTIVATED = "deactivated"


class AcceptanceRecordStatus(StrEnum):
    DRAFT = "draft"
    PRE_SCREENING = "pre_screening"
    AWAITING_PARTNER = "awaiting_partner"
    DECIDED = "decided"
    DECLINED = "declined"


class LetterStatus(StrEnum):
    NOT_STARTED = "not_started"
    DRAFT = "draft"
    PARTNER_APPROVED = "partner_approved"
    SENT = "sent"
    SIGNED = "signed"
    NOT_REQUIRED = "not_required"
    SUPERSEDED = "superseded"


class LetterClauseStatus(StrEnum):
    ON = "on"
    OFF = "off"
    REQUIRED = "required"


class LetterRecordStatus(StrEnum):
    NOT_SIGNED = "not_signed"
    SIGNED = "signed"


class ConflictAssessmentStatus(StrEnum):
    PENDING = "pending"
    CLEAR = "clear"
    SAME_FAMILY_NOT_ADVERSE = "same_family_not_adverse"
    NOT_ADVERSE = "not_adverse"
    COUNTERPARTY_REVIEW = "counterparty_review"
    CONFLICT = "conflict"


class NasEvaluationStatus(StrEnum):
    PENDING = "pending"
    CONCLUDED = "concluded"
    NOT_APPLICABLE = "not_applicable"


class IndependenceConclusionStatus(StrEnum):
    INDEPENDENT = "independent"
    INDEPENDENT_WITH_SAFEGUARDS = "independent_with_safeguards"
    NOT_INDEPENDENT = "not_independent"


class CitationStatus(StrEnum):
    pass
    # derived, never stored: valid, moved, broken, relinked


class ViewerStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    PASSWORD_PROTECTED = "password_protected"
    UNREADABLE = "unreadable"
    NOT_PREVIEWABLE = "not_previewable"


class EvidenceUnlockStatus(StrEnum):
    READY = "ready"
    WRONG_PASSWORD = "wrong_password"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    DEACTIVATED = "deactivated"


class AnnualIndependenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    NOT_YET = "not_yet"
    DECLINED = "declined"


class WallApprovalStatus(StrEnum):
    AWAITING = "awaiting"
    APPROVED = "approved"


class LegalHoldStatus(StrEnum):
    APPLYING = "applying"
    ACTIVE = "active"
    RELEASING = "releasing"
    RELEASED = "released"


class AiPolicyVersionStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    PUBLISHED = "published"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    # derived, never stored: superseded


class SecurityIncidentStatus(StrEnum):
    INVESTIGATING = "investigating"
    CLOSED = "closed"


class FirmExportStatus(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    READY = "ready"
    DOWNLOADED = "downloaded"
    EXPIRED = "expired"


class FirmExportScheduleStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    PAUSED = "paused"


class SafeguardsControlStatus(StrEnum):
    EVIDENCED = "evidenced"
    OPEN = "open"


class SupportSessionStatus(StrEnum):
    REQUESTED = "requested"
    ACTIVE = "active"
    DECLINED = "declined"
    REVOKED = "revoked"


class ClientInvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SampleSetVersionStatus(StrEnum):
    DRAWING = "drawing"
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class CompletenessTieResultStatus(StrEnum):
    TIE = "tie"
    OFF = "off"
    CHECK = "check"


class MappingSetStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    PREPARED = "prepared"
    REVIEWED = "reviewed"
    CHANGED_AFTER_SIGN_OFF = "changed_after_sign_off"


class AccountMappingStateStatus(StrEnum):
    UNMAPPED = "unmapped"
    RULE = "rule"
    EDITED = "edited"
    SUGGESTED = "suggested"
    ADOPTED = "adopted"


class WorkpaperValueStateStatus(StrEnum):
    EMPTY = "empty"
    SUGGESTED = "suggested"
    ADOPTED = "adopted"
    EDITED = "edited"
    HUMAN = "human"


class AttentionFlagStatus(StrEnum):
    OPEN = "open"
    CONVERTED = "converted"
    RESOLVED = "resolved"


class AuditProcedureStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETE = "complete"


class MaterialityVersionStatus(StrEnum):
    PROPOSED = "proposed"
    DECIDED = "decided"
    REASSESSED = "reassessed"
    REVISED = "revised"
    # derived, never stored: superseded


class RiskRegisterRowStatus(StrEnum):
    DRAFT = "draft"
    EP_APPROVED = "ep_approved"
    REVISED = "revised"


class RiskSignificanceStatus(StrEnum):
    NONE = "none"
    MANDATORY = "mandatory"
    PROPOSED = "proposed"
    APPROVED = "approved"
    NOT_SIGNIFICANT = "not_significant"


class RiskFraudStatus(StrEnum):
    NONE = "none"
    PRESUMED = "presumed"
    REBUTTAL_PROPOSED = "rebuttal_proposed"
    REBUTTAL_APPROVED = "rebuttal_approved"


class RiskLinkageStatus(StrEnum):
    LINKED = "linked"
    SUGGESTED = "suggested"


class FraudMinutesStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"


class FraudInquiryStatus(StrEnum):
    REQUESTED = "requested"
    ANSWERED = "answered"


class ServiceOrganizationStatus(StrEnum):
    PENDING = "pending"
    GAP_FOUND = "gap_found"
    BRIDGE_LETTER_RECEIVED = "bridge_letter_received"
    RELIANCE_CONCLUDED = "reliance_concluded"
    CERTIFICATION_ACCEPTED = "certification_accepted"
    NO_RELIANCE = "no_reliance"
    NOT_RELEVANT = "not_relevant"


class SocRelianceStatus(StrEnum):
    PENDING = "pending"
    RELIED = "relied"
    NOT_RELIED = "not_relied"


class CuecStatus(StrEnum):
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCED = "evidenced"


class ControlDesignStatus(StrEnum):
    EFFECTIVE = "effective"
    DEFICIENT = "deficient"
    NOT_ASSESSED = "not_assessed"


class ControlExceptionDispositionStatus(StrEnum):
    EXCEPTION_FOR_RESOLUTION = "exception_for_resolution"
    PROPOSED = "proposed"


class EbpProviderCheckStatus(StrEnum):
    RECEIVED = "received"
    WAITING_ON_INPUTS = "waiting_on_inputs"
    CORRECTION_REQUESTED = "correction_requested"


class EbpLateRemittanceStatus(StrEnum):
    FOUND = "found"
    PENDING_VFCP_SCC = "pending_vfcp_scc"
    CORRECTED = "corrected"


class EbpForm5330Status(StrEnum):
    EXPOSURE = "exposure"
    NOT_REQUIRED = "not_required"
    FILED = "filed"


class EbpCertificationPointStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    EVALUATED = "evaluated"


class EbpForm5500LineStatus(StrEnum):
    pass
    # derived, never stored: tie, reconciling_item, inconsistent


class EbpPartIvStatus(StrEnum):
    pass
    # derived, never stored: consistent, inconsistent


class EbpTestResultStatus(StrEnum):
    UNTESTED = "untested"
    TESTING = "testing"
    PASS = "pass"
    EXCEPTION = "exception"
    NEEDS_HUMAN = "needs_human"
    NO_EFFECT = "no_effect"


class Aud27ItemStatus(StrEnum):
    UNEVALUATED = "unevaluated"
    EVALUATED = "evaluated"
    EXCEPTION = "exception"
    SCREENED_OUT = "screened_out"


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
    "engine_import": (
        "scanning",
        "pending_approval",
        "approved",
        "rejected",
        "routed",
    ),
    "k3": (
        "included",
        "not_required",
        "not_included",
    ),
    "transcript_parse": (
        "queued",
        "parsed",
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
    "questionnaire": (
        "open",
        "complete",
        "submitted",
    ),
    "recipient_details_change": (
        "pending",
        "accepted",
        "rejected",
    ),
    "k1_handoff": (
        "awaiting",
        "received",
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
    "engagement_export": (
        "queued",
        "packaging",
        "ready",
        "failed",
        "expired",
        "undone",
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
    "trial_balance_label": (
        "standard",
        "interim",
        "prior",
        "budget",
        "preliminary",
    ),
    "trial_balance_layer": (
        "unadjusted",
        "aje",
        "rje",
        "final",
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
        "held",
        "withdrawn",
    ),
    "inbox_thread": (
        "unmatched",
        "matched",
        "ignored",
    ),
    "portal_intake_upload": (
        "sent",
        "received",
        "withdrawn",
    ),
    "file_document": (
        "processing",
        "needs_review",
        "accepted",
        "superseded",
        "on_hold",
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
    "sign_off_slot": (
    ),
    "human_gate": (
        "open",
        "done",
        "voided",
    ),
    "due_risk": (
    ),
    "decision_card": (
        "awaiting_role",
        "decided",
        "superseded",
    ),
    "field_value": (
    ),
    "comment_thread": (
        "open",
        "resolved",
    ),
    "todo": (
        "open",
        "done",
    ),
    "methodology_version": (
        "draft",
        "parsing",
        "needs_review",
        "published",
        "superseded",
        "discarded",
    ),
    "methodology_import": (
        "awaiting_files",
        "scanning",
        "parsing",
        "needs_review",
        "failed",
        "cancelled",
    ),
    "knowledge_item": (
        "draft",
        "published",
        "superseded",
    ),
    "tax_authorization": (
        "requested",
        "on_file",
        "expired",
        "revoked",
    ),
    "efile_ack": (
        "accepted",
        "rejected",
    ),
    "firm_standard_version": (
        "draft",
        "published",
        "discarded",
    ),
    "reference_set_version": (
        "draft",
        "published",
        "withdrawn",
    ),
    "parse_flag": (
        "low_confidence",
        "split_across_pages",
        "numbering_gap",
        "unverified_citation",
        "cross_reference_missing",
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
    "envelope_signer": (
        "pending",
        "viewed",
        "verified",
        "signed",
        "declined",
        "verification_failed",
    ),
    "signing_step": (
    ),
    "envelope_purpose": (
        "e_file_authorization",
        "engagement_letter",
        "representation_letter",
        "consent_7216",
    ),
    "generated_document": (
        "drafting",
        "draft",
        "approved",
        "locked",
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
        "superseded",
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
    "suggestion": (
        "pending",
        "adopted",
        "edited",
        "dismissed",
        "superseded",
        "expired",
    ),
    "proposal": (
        "pending",
        "approved",
        "approved_with_edits",
        "rejected",
        "superseded",
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
        "saved",
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
    "client": (
        "prospect",
        "active",
        "inactive",
        "former",
    ),
    "invitation": (
        "not_invited",
        "invited",
        "active",
        "locked",
        "deactivated",
    ),
    "acceptance_record": (
        "draft",
        "pre_screening",
        "awaiting_partner",
        "decided",
        "declined",
    ),
    "letter": (
        "not_started",
        "draft",
        "partner_approved",
        "sent",
        "signed",
        "not_required",
        "superseded",
    ),
    "letter_clause": (
        "on",
        "off",
        "required",
    ),
    "letter_record": (
        "not_signed",
        "signed",
    ),
    "conflict_assessment": (
        "pending",
        "clear",
        "same_family_not_adverse",
        "not_adverse",
        "counterparty_review",
        "conflict",
    ),
    "nas_evaluation": (
        "pending",
        "concluded",
        "not_applicable",
    ),
    "independence_conclusion": (
        "independent",
        "independent_with_safeguards",
        "not_independent",
    ),
    "citation": (
    ),
    "viewer": (
        "processing",
        "ready",
        "password_protected",
        "unreadable",
        "not_previewable",
    ),
    "evidence_unlock": (
        "ready",
        "wrong_password",
    ),
    "membership": (
        "active",
        "invited",
        "deactivated",
    ),
    "annual_independence": (
        "confirmed",
        "not_yet",
        "declined",
    ),
    "wall_approval": (
        "awaiting",
        "approved",
    ),
    "legal_hold": (
        "applying",
        "active",
        "releasing",
        "released",
    ),
    "ai_policy_version": (
        "draft",
        "awaiting_approval",
        "published",
        "declined",
        "withdrawn",
    ),
    "security_incident": (
        "investigating",
        "closed",
    ),
    "firm_export": (
        "awaiting_approval",
        "ready",
        "downloaded",
        "expired",
    ),
    "firm_export_schedule": (
        "pending_approval",
        "active",
        "paused",
    ),
    "safeguards_control": (
        "evidenced",
        "open",
    ),
    "support_session": (
        "requested",
        "active",
        "declined",
        "revoked",
    ),
    "client_invitation": (
        "pending",
        "accepted",
        "revoked",
        "expired",
    ),
    "sample_set_version": (
        "drawing",
        "draft",
        "approved",
        "superseded",
        "failed",
    ),
    "completeness_tie_result": (
        "tie",
        "off",
        "check",
    ),
    "mapping_set": (
        "in_progress",
        "prepared",
        "reviewed",
        "changed_after_sign_off",
    ),
    "account_mapping_state": (
        "unmapped",
        "rule",
        "edited",
        "suggested",
        "adopted",
    ),
    "workpaper_value_state": (
        "empty",
        "suggested",
        "adopted",
        "edited",
        "human",
    ),
    "attention_flag": (
        "open",
        "converted",
        "resolved",
    ),
    "audit_procedure": (
        "not_started",
        "in_progress",
        "in_review",
        "complete",
    ),
    "materiality_version": (
        "proposed",
        "decided",
        "reassessed",
        "revised",
    ),
    "risk_register_row": (
        "draft",
        "ep_approved",
        "revised",
    ),
    "risk_significance": (
        "none",
        "mandatory",
        "proposed",
        "approved",
        "not_significant",
    ),
    "risk_fraud": (
        "none",
        "presumed",
        "rebuttal_proposed",
        "rebuttal_approved",
    ),
    "risk_linkage": (
        "linked",
        "suggested",
    ),
    "fraud_minutes": (
        "draft",
        "awaiting_approval",
        "approved",
    ),
    "fraud_inquiry": (
        "requested",
        "answered",
    ),
    "service_organization": (
        "pending",
        "gap_found",
        "bridge_letter_received",
        "reliance_concluded",
        "certification_accepted",
        "no_reliance",
        "not_relevant",
    ),
    "soc_reliance": (
        "pending",
        "relied",
        "not_relied",
    ),
    "cuec": (
        "evidence_missing",
        "evidenced",
    ),
    "control_design": (
        "effective",
        "deficient",
        "not_assessed",
    ),
    "control_exception_disposition": (
        "exception_for_resolution",
        "proposed",
    ),
    "ebp_provider_check": (
        "received",
        "waiting_on_inputs",
        "correction_requested",
    ),
    "ebp_late_remittance": (
        "found",
        "pending_vfcp_scc",
        "corrected",
    ),
    "ebp_form5330": (
        "exposure",
        "not_required",
        "filed",
    ),
    "ebp_certification_point": (
        "not_evaluated",
        "evaluated",
    ),
    "ebp_form5500_line": (
    ),
    "ebp_part_iv": (
    ),
    "ebp_test_result": (
        "untested",
        "testing",
        "pass",
        "exception",
        "needs_human",
        "no_effect",
    ),
    "aud27_item": (
        "unevaluated",
        "evaluated",
        "exception",
        "screened_out",
    ),
}
CHECKS: dict[str, str] = {
    name: "(" + ", ".join(f"'{code}'" for code in codes) + ")"
    for name, codes in STORED.items()
}
