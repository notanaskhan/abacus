"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.ai_gateway import (
    BoundaryFactsChanged,
    on_boundary_facts_changed,
    register_client_data_facts,
)
from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.agents.activities import ACTIVITIES
from abacus.modules.agents.ai_policy_contract import ai_policy_router
from abacus.modules.agents.ai_policy_errors import AiPolicyLoosened, ApproverMustDiffer
from abacus.modules.agents.ai_policy_service import Effective as EffectiveAiPolicy
from abacus.modules.agents.ai_policy_service import effective_ai_policy
from abacus.modules.agents.ai_policy_store import policy_autonomy_level
from abacus.modules.agents.approved_writes import SUBSCRIPTIONS as APPROVED_WRITE_SUBSCRIPTIONS
from abacus.modules.agents.approved_writes import register_file_writes
from abacus.modules.agents.audit_targets import AUDIT_KINDS, audit_owners

# P-10-T43 (DEC-4301): a workbench session's turns are runs; workbench runs them inline.
# P-10-T44 (DEC-4302): frozen trace exports, the run_events prune and A-07's archive hook.
from abacus.modules.agents.capability_availability import capability_ready as capability_ready
from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.code_runs import (  # A-07-T32: code-only runs, v1 path
    CodeRun,
    CodeStep,
    ReservedAction,
    begin_code_run,
    blocks,
    fact,
    fail_code_run,
    finish_code_run,
    record_code_run,
    text_part,
    txt,
)
from abacus.modules.agents.contract import proposals_router, suggestions_router
from abacus.modules.agents.decision_recommend import (
    RECOMMENDER,
    OptionFact,
    PriorFact,
    Recommended,
    RecommendFacts,
    recommend,
)
from abacus.modules.agents.engagement_agent import start_agents
from abacus.modules.agents.engagement_agent_workflow import HANDLE as ENGAGEMENT_AGENT_HANDLE
from abacus.modules.agents.engagement_agent_workflow import (
    NEXT_TICK as ENGAGEMENT_AGENT_NEXT_TICK,
)
from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.engagement_run import PlanProviderUnavailable as PlanProviderUnavailable

# T-05-T31 (DEC-4616): a work item's owner supplies the run's code plan.
from abacus.modules.agents.engagement_run import PlanRequest as PlanRequest
from abacus.modules.agents.engagement_run import (  # P-10-T39: the run-step slot's owners
    RunStepFacts as RunStepFacts,
)
from abacus.modules.agents.engagement_run import RunStepResult as RunStepResult
from abacus.modules.agents.engagement_run import WorkItemRun as WorkItemRun
from abacus.modules.agents.engagement_run import register_plan_provider as register_plan_provider
from abacus.modules.agents.engagement_run import register_run_step as register_run_step
from abacus.modules.agents.engagement_run import start_engagement_run as start_engagement_run
from abacus.modules.agents.engagement_run import work_item_runs as work_item_runs
from abacus.modules.agents.engagement_runs import (
    ActiveRun,
    active_engagement_runs,
    register_engagement_run_agent,
)
from abacus.modules.agents.entry_assess import ASSESSOR, ask, check
from abacus.modules.agents.events import FollowUpSent
from abacus.modules.agents.events import SectionDraftFinished as SectionDraftFinished
from abacus.modules.agents.export_screening import screening_section
from abacus.modules.agents.fake_responses import (
    SCREEN_PROMPT,
    review_sha256,
    screening_responder,
)
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.fake_responses import install_review as install_fake_reviews
from abacus.modules.agents.field_citations import register_field_citations_reader
from abacus.modules.agents.follow_up_drafts import draft_for as draft_follow_ups
from abacus.modules.agents.follow_up_drafts import on_follow_up_sent
from abacus.modules.agents.follow_up_routes import follow_ups_router
from abacus.modules.agents.follow_ups import reminder_history_of
from abacus.modules.agents.gates import register_gate_sources, register_suggestion_lookup
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.guidance_draft import DRAFTER, DraftOutcome, create_draft_run, draft
from abacus.modules.agents.handoff import (
    Citation,
    DraftCitation,
    DraftedCell,
    Handoff,
    ImportBatchOutput,
    ImportedProgram,
    ImportedStep,
    ScreeningOutput,
    SectionDraft,
    VerifiedCitation,
)
from abacus.modules.agents.handoff import NoticeAnalyzeOutput as NoticeAnalyzeOutput
from abacus.modules.agents.handoff import NoticeExtractOutput as NoticeExtractOutput
from abacus.modules.agents.home_counts import register_home_counts
from abacus.modules.agents.inbox_match import MATCHER, MatchOutcome, create_match_run, match
from abacus.modules.agents.intake_candidates import intake_candidates
from abacus.modules.agents.intake_match import IntakeOutcome, create_intake_match_run, match_intake
from abacus.modules.agents.issue_client_requests import send_issue_to_client
from abacus.modules.agents.knowledge import KnowledgeHit, knowledge_context, search_knowledge
from abacus.modules.agents.methodology_citations import register_methodology_step
from abacus.modules.agents.methodology_import_workflow import MethodologyImportWorkflow
from abacus.modules.agents.notice_responder import RESPONDER as RESPONDER
from abacus.modules.agents.notice_responder import AnalyzeFacts as AnalyzeFacts
from abacus.modules.agents.notice_responder import analyze as analyze_notice
from abacus.modules.agents.notice_responder import build_context as notice_context
from abacus.modules.agents.notice_responder import check as check_notice_answer
from abacus.modules.agents.notice_responder import extract_fields as extract_notice_fields
from abacus.modules.agents.pilot_w7 import w7_override_rate
from abacus.modules.agents.proposal_slots import (
    AdoptedValue,
    ApprovedChangeSet,
    ChangeSetApplier,
    ProposedValue,
    SuggestionApplier,
    ThresholdEvaluation,
    ThresholdPolicy,
    UnregisteredTarget,
    apply_proposal,
    check_suggestion_target,
    register_change_set_applier,
    register_proposal_adapter,
    register_suggestion_applier,
    register_suggestion_target,
    register_threshold_policy,
)
from abacus.modules.agents.proposals import (
    PendingFieldSuggestion,
    PendingSuggestion,
    ProposalChanged,
    ProposalInvalid,
    ProposedRow,
    SuggestionChanged,
    create_proposal,
    create_suggestion,
    pending_suggestion,
    pending_suggestions,
    register_checkpoint_hooks,
    register_proposal_state,
)
from abacus.modules.agents.review_start import (
    CitationStates,
    ReviewUnavailable,
    request_review,
    review_citation_states,
)
from abacus.modules.agents.routes import (
    graph_router,
    knowledge_router,
    router,
    template_drafts_router,
)
from abacus.modules.agents.run_activities import PlanState as RunV2PlanState
from abacus.modules.agents.run_activities import RunFacts as RunV2Facts
from abacus.modules.agents.run_activities import StepOutcome as RunV2StepOutcome
from abacus.modules.agents.run_artifacts_contract import (
    run_artifacts_router,
    session_drill_router,
)
from abacus.modules.agents.run_backfill import register_session_links
from abacus.modules.agents.run_backfill_workflow import (
    BACKFILL_ID_PREFIX,
    AgentRunBackfillWorkflow,
    BackfillBatch,
    BackfillInput,
)
from abacus.modules.agents.run_events_prune_workflow import (
    RunEventsPruneWorkflow as RunEventsPruneWorkflow,
)
from abacus.modules.agents.run_logs import (  # A-07-T31/T32: binder section G, bring-down
    last_completed_run,
    last_completed_run_at,
    run_log_count,
    run_record_hashes,  # A-07-T37: the archive seal's run-record leaves
)
from abacus.modules.agents.run_plan import PlanStep as PlanStep
from abacus.modules.agents.run_plan import reserved as reserved_plan_tools

# P-10-T22 (C17 v1, frozen): the runtime the harness calls, and the shapes a tool declares.
from abacus.modules.agents.run_recorder import (  # P-09-T12: the synthetic scenario's runs
    RecordedRun,
    RecordedStep,
    StepAdvance,
    advance_synthetic_step,
    record_synthetic_run,
)
from abacus.modules.agents.run_stream import badge_stream as agent_badge_stream  # P-10-T26

# DEC-4417: an owner's own decision cards held by a run step (planning materiality).
from abacus.modules.agents.run_waits import HeldCard as HeldCard
from abacus.modules.agents.run_waits import on_decision_decided
from abacus.modules.agents.run_waits import register_decision_source as register_decision_source
from abacus.modules.agents.run_waits import run_workflow_id as run_workflow_id
from abacus.modules.agents.run_workflow import AgentRunInput as AgentRunInput
from abacus.modules.agents.run_workflow import AgentRunWorkflow as AgentRunWorkflow
from abacus.modules.agents.runs import run_initiators
from abacus.modules.agents.runs_routes import engagement_runs_router, runs_router
from abacus.modules.agents.runs_v2_contract import (
    capabilities_router,
    engagement_runs_v2_router,
    feedback_router,
    runs_v2_router,
)
from abacus.modules.agents.screening_contract import screening_items_router, screenings_router
from abacus.modules.agents.screenings import (
    SUBSCRIPTIONS as SCREENING_SUBSCRIPTIONS,
)
from abacus.modules.agents.screenings import (
    WORKFLOWS,
    start_screening,
    workflow_id,
)
from abacus.modules.agents.section_draft import (
    DraftCapReached as DraftCapReached,
)
from abacus.modules.agents.section_draft import DraftingNotEnabled
from abacus.modules.agents.section_draft import (
    followed_up_running as followed_up_running,
)
from abacus.modules.agents.section_draft import start as start_section_draft
from abacus.modules.agents.section_sources import (
    ModeDocument,
    ModeInputs,
    ModeMapping,
    ModePage,
    ModeTarget,
    PackProblem,
    PackRefused,
    SectionSource,
    SourceCell,
    SourcePaper,
    register_mode_mapping,
    register_mode_plan,
    register_mode_preparer,
    register_section_source,
)
from abacus.modules.agents.service import (
    SCREENER,
    AgentRunBusy,
    AgentRunNotRunning,
    RunOutcome,
    ScreeningOutcome,
    ScreeningResultView,
    create_screening_run,
    fail_run,
    load_agent_context,
    proposal_of,
    proposals_for,
    run_outcome,
    run_v2_status,
    screen,
    screening_results_for,
)
from abacus.modules.agents.session_subjects import (
    register_session_subject as register_session_subject,
)
from abacus.modules.agents.session_subjects import subject_engagement as subject_engagement
from abacus.modules.agents.session_turns import TurnOutcome as TurnOutcome
from abacus.modules.agents.session_turns import dispatch_run as dispatch_run
from abacus.modules.agents.session_turns import open_plan_child_run as open_plan_child_run
from abacus.modules.agents.session_turns import open_turn_run as open_turn_run
from abacus.modules.agents.session_turns import run_session_turn as run_session_turn
from abacus.modules.agents.shadow_score import (
    DecidedNotice,
    OverrideRate,
    ShadowScore,
    live_override,
    override_rate,
    register_notice_shadows,
    shadow_score,
)
from abacus.modules.agents.spec import AGENTS, AgentSpec, cleared_for_client_data, spec
from abacus.modules.agents.stage_admin import (
    NamedReport,
    ShadowReportChanged,
    ShadowReportRequired,
    ShadowReportStale,
    StageNotReady,
    check_live,
)
from abacus.modules.agents.stage_routes import platform_stages_router
from abacus.modules.agents.stages import assistants, stage_for, starts_in_shadow

# P-10-T28: importing the catalogue registers every module's declared tools.
from abacus.modules.agents.tools.catalogue import DECLARED as DECLARED
from abacus.modules.agents.tools.registry import AgentTool as AgentTool
from abacus.modules.agents.tools.registry import ToolNotRegistered as ToolNotRegistered
from abacus.modules.agents.tools.registry import ToolPageIn as ToolPageIn
from abacus.modules.agents.tools.registry import ToolPageOut as ToolPageOut
from abacus.modules.agents.tools.registry import agent_tool as agent_tool
from abacus.modules.agents.tools.registry import has_never_verb
from abacus.modules.agents.tools.registry import register_tool as register_tool
from abacus.modules.agents.tools.registry import registered_tools as registered_tools
from abacus.modules.agents.tools.runtime import ToolCallIn as ToolCallIn
from abacus.modules.agents.tools.runtime import ToolOutcome as ToolOutcome
from abacus.modules.agents.tools.runtime import ToolTargets as ToolTargets
from abacus.modules.agents.tools.runtime import call_tool as call_tool
from abacus.modules.agents.tools.runtime import for_model as tool_output_for_model
from abacus.modules.agents.trace_records import PRUNE_SCHEDULES as SCHEDULES
from abacus.modules.agents.trace_records import AdoptedTrace as AdoptedTrace
from abacus.modules.agents.trace_records import adopted_run_traces as adopted_run_traces
from abacus.modules.agents.upload_review import (
    REVIEWER,
    ReviewOutcome,
    create_review_run,
    review,
)
from abacus.modules.agents.upload_review import model_available as upload_review_available
from abacus.modules.agents.usage_labels import capability_labels
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    EntryAssessInput,
    EntryAssessRunInput,
    GuidanceDraftInput,
    GuidanceDraftRunInput,
    HandleInput,
    HandleResult,
    ImportBatchInput,
    ImportBatchOutcome,
    ImportFailInput,
    ImportFinishInput,
    ImportPagesOutcome,
    MatchInput,
    MatchRunInput,
    MethodologyImportInput,
    NextTickInput,
    RunInput,
    ScreeningInput,
    SectionDraftInput,
    SlotGrant,
)
from abacus.modules.agents.workflows import (
    EntryAssessWorkflow,
    GuidanceDraftWorkflow,
    InboxMatchWorkflow,
    ScreeningWorkflow,
    SectionDraftWorkflow,
    UploadReviewWorkflow,
)
from abacus.modules.communications.api import register_intake_candidates, register_reminder_history
from abacus.modules.evidence.api import register_export_section, register_proposal_source
from abacus.modules.identity.api import (
    AbacusRouter,
    register_ai_assistants,
    register_autonomy_level_provider,
)
from abacus.modules.platform.api import register_pilot_metric_source, register_usage_labeller
from abacus.modules.review.api import register_client_request_sender, register_run_status_reader

# P-10-T38: `file_save` proposals hold their effect on a grant (approved_writes.py).
register_file_writes()
# P-10-T42: the platform's agent-minute reads name capabilities through this module (ADR-008).
register_usage_labeller("capability", capability_labels)
# Evidence owns review decisions; agents owns what was proposed (TASK-019 D1).
register_proposal_source(proposals_for, proposal_of)
# A-01-T19 (SPEC-344 §6): screening results are the export's `provenance/screening.csv`.
register_export_section("screening", screening_section)
# SPEC-036 (TASK-075): which agents may see a real firm's data (stages follow in TASK-076).
register_client_data_facts(cleared=cleared_for_client_data, stage=stage_for)
# SPEC-036 (TASK-076): identity's disclosure lists the cleared assistants and their stage.
register_ai_assistants(assistants)
# G-02-T23 (DEC-711): the AI policy's level, where the policy governs the firm.
register_autonomy_level_provider(policy_autonomy_level)

# The routers the API mounts, in order (P-39; F-03-T07).
# K-01-T12: C4's `methodology_step` citable (agents imports evidence and methodology).
register_methodology_step()

ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    graph_router,
    knowledge_router,
    template_drafts_router,
    engagement_runs_router,
    runs_router,
    engagement_runs_v2_router,
    runs_v2_router,
    feedback_router,
    capabilities_router,
    # W-02-T03: run-artifact preview and download, the session drill (stubs).
    run_artifacts_router,
    session_drill_router,
    # C3 (P-04-T08; ADR-161); `review.grammar_api` retired (P-04-T62).
    proposals_router,
    suggestions_router,
    follow_ups_router,  # P-06-T14: follow-ups v2 behind `binders.engine`
    # C5 v1.2 SHL-20 family stub behind `screening.card` (P-06-T15).
    screening_items_router,
    screenings_router,
    platform_stages_router,  # Q-02-T07: platform staff set an agent's stage for a firm
    ai_policy_router,  # G-02-T15: the AI-policy family stub behind `ai_policy.v1`
)
# P-06-T14: a sent follow-up's email leaves when the relay delivers its grant-held event.
# Q-02-T08: a firm's changed boundary facts are forgotten in the worker too.
SUBSCRIPTIONS = {
    **SCREENING_SUBSCRIPTIONS,
    # P-10-T38: a decided or undone proposal re-derives its run; an approval starts its write.
    **APPROVED_WRITE_SUBSCRIPTIONS,
    # P-10-T32 (AC-W4): a decided card resumes the run branch held on it.
    "decision.decided": on_decision_decided,
    FollowUpSent.event_type: on_follow_up_sent,
    BoundaryFactsChanged.event_type: on_boundary_facts_changed,
}

# P-04-T16 (C13): the agent's proposals are `proposal` gates until a person decides.
register_gate_sources()
# I-01-T08: this module's HOME-01 tile or pill (platform.register_home_count).
register_home_counts()
# P-04-T23: review checks a decision card's recommended suggestion against its engagement.
register_suggestion_lookup()
# P-04-T26 (C16): what a proposal says now, for the drawer's facts and Approvals.
register_proposal_state()
# P-04-T32 (DEC-804): a proposal's checkpoint is decided through the proposal (SHL-16 = SHL-10).
register_checkpoint_hooks()
# P-04-T35 (DEC-1050): SHL-09's citations are checked, shown and written through C4 here.
register_field_citations_reader()

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# R-01-T24 security review M-a: communications checks a scheduled Reminder against what was sent.
register_reminder_history(reminder_history_of)
# N-01-T22 follow-up (DEC-1287): INB-02's cards read the matcher's shown intake proposals.
register_intake_candidates(intake_candidates)

register_pilot_metric_source("w7", w7_override_rate)  # Q-04-T008 (DEC-825)
register_client_request_sender(send_issue_to_client)  # P-04-T31 (DEC-828)
register_run_status_reader(run_v2_status)  # T-04-T29: the issue detail's fix-run state

# P-10-T38: the approved-write workflow and its types, for the history recorder.
from abacus.modules.agents.approved_write_workflow import (  # noqa: E402
    ApprovedWriteInput as ApprovedWriteInput,
)
from abacus.modules.agents.approved_write_workflow import (  # noqa: E402
    ApprovedWriteWorkflow as ApprovedWriteWorkflow,
)
from abacus.modules.agents.approved_write_workflow import (  # noqa: E402
    approved_write_id as approved_write_id,
)

# The C6 v1.1 blocks schema and the spec v2 checks, for their generators (S31 end pass; BOUND-001).
from abacus.modules.agents.blocks import AgentBlocks, BlocksTurn, Fact  # noqa: E402
from abacus.modules.agents.det_runs import (  # noqa: E402 -- A-06-T25
    close_deterministic_run,
    deterministic_run_facts,
    open_deterministic_run,
)

# T-04-T15: an owner's applier reads an approved proposal's rows (never a pending one).
from abacus.modules.agents.proposal_store import (  # noqa: E402
    approved_rows as approved_proposal_rows,
)
from abacus.modules.agents.proposal_store import (  # noqa: E402 -- T-04-T36
    approver_of as proposal_approver,
)
from abacus.modules.agents.run_activities import (  # noqa: E402 -- the history recorder's types
    PlanState,
    RunFacts,
    StepOutcome,
)
from abacus.modules.agents.run_start import open_capability_run  # noqa: E402 -- T-04-T25
from abacus.modules.agents.run_waits import WaitState  # noqa: E402 -- the history recorder's
from abacus.modules.agents.service import load_run_v2_context  # noqa: E402 -- T-04-T25
from abacus.modules.agents.spec_v2 import (  # noqa: E402
    AgentSpecV2,
    ToolFacts,
    registry_problems,
    spec_problems,
    spec_v2,  # T-04-T25: a capability's v2 spec (the drafter's tier, limits, routes)
)

__all__ = [
    "ACTIVITIES",
    "AGENTS",
    "ASSESSOR",
    "BACKFILL_ID_PREFIX",
    "DRAFTER",
    "ENGAGEMENT_AGENT_HANDLE",
    "ENGAGEMENT_AGENT_NEXT_TICK",
    "MATCHER",
    "RECOMMENDER",
    "REVIEWER",
    "ROUTERS",
    "SCHEDULES",
    "SCREENER",
    "SCREEN_PROMPT",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ActiveRun",
    "AdoptedTrace",
    "AdoptedValue",
    "AgentBlocks",
    "AgentEvent",
    "AgentInput",
    "AgentRunBackfillWorkflow",
    "AgentRunBusy",
    "AgentRunInput",
    "AgentRunNotRunning",
    "AgentRunWorkflow",
    "AgentSpec",
    "AgentSpecV2",
    "AiPolicyLoosened",
    "AnalyzeFacts",
    "ApprovedChangeSet",
    "ApproverMustDiffer",
    "BackfillBatch",
    "BackfillInput",
    "BatchOutcome",
    "BlocksTurn",
    "ChangeSetApplier",
    "Citation",
    "CitationStates",
    "CodeRun",
    "CodeStep",
    "DecidedNotice",
    "DraftCitation",
    "DraftOutcome",
    "DraftedCell",
    "DraftingNotEnabled",
    "EffectiveAiPolicy",
    "EngagementAgent",
    "EngagementGraph",
    "EntryAssessInput",
    "EntryAssessRunInput",
    "EntryAssessWorkflow",
    "Fact",
    "FailKnowledgeInput",
    "GuidanceDraftInput",
    "GuidanceDraftRunInput",
    "GuidanceDraftWorkflow",
    "HandleInput",
    "HandleResult",
    "Handoff",
    "HeldCard",
    "ImportBatchInput",
    "ImportBatchOutcome",
    "ImportBatchOutput",
    "ImportFailInput",
    "ImportFinishInput",
    "ImportPagesOutcome",
    "ImportedProgram",
    "ImportedStep",
    "InboxMatchWorkflow",
    "IntakeOutcome",
    "KnowledgeEmbeddingWorkflow",
    "KnowledgeHit",
    "KnowledgeInput",
    "MatchInput",
    "MatchOutcome",
    "MatchRunInput",
    "MethodologyImportInput",
    "MethodologyImportWorkflow",
    "ModeDocument",
    "ModeInputs",
    "ModeMapping",
    "ModePage",
    "ModeTarget",
    "NamedReport",
    "NextTickInput",
    "OptionFact",
    "OverrideRate",
    "PackProblem",
    "PackRefused",
    "PendingFieldSuggestion",
    "PendingSuggestion",
    "PlanState",
    "PriorFact",
    "ProposalChanged",
    "ProposalInvalid",
    "ProposedRow",
    "ProposedValue",
    "RecommendFacts",
    "Recommended",
    "RecordedRun",
    "RecordedStep",
    "ReservedAction",
    "ReviewOutcome",
    "ReviewUnavailable",
    "RunEventsPruneWorkflow",
    "RunFacts",
    "RunInput",
    "RunOutcome",
    "RunV2Facts",
    "RunV2PlanState",
    "RunV2StepOutcome",
    "ScreeningInput",
    "ScreeningOutcome",
    "ScreeningOutput",
    "ScreeningResultView",
    "ScreeningWorkflow",
    "SectionDraft",
    "SectionDraftFinished",
    "SectionDraftInput",
    "SectionDraftWorkflow",
    "SectionSource",
    "ShadowReportChanged",
    "ShadowReportRequired",
    "ShadowReportStale",
    "ShadowScore",
    "SheetLayoutError",
    "SlotGrant",
    "SourceCell",
    "SourcePaper",
    "StageNotReady",
    "StepAdvance",
    "StepOutcome",
    "SuggestionApplier",
    "SuggestionChanged",
    "ThresholdEvaluation",
    "ThresholdPolicy",
    "ToolFacts",
    "TurnOutcome",
    "UnregisteredTarget",
    "UploadReviewWorkflow",
    "VerifiedCitation",
    "WaitState",
    "active_engagement_runs",
    "adopted_run_traces",
    "advance_synthetic_step",
    "agent_badge_stream",
    "analyze_notice",
    "apply_proposal",
    "approved_proposal_rows",
    "ask",
    "begin_code_run",
    "blocks",
    "capability_ready",
    "check",
    "check_live",
    "check_notice_answer",
    "check_suggestion_target",
    "close_deterministic_run",
    "create_draft_run",
    "create_intake_match_run",
    "create_match_run",
    "create_proposal",
    "create_review_run",
    "create_screening_run",
    "create_suggestion",
    "deterministic_run_facts",
    "dispatch_run",
    "draft",
    "draft_follow_ups",
    "effective_ai_policy",
    "engagement_graph",
    "extract_notice_fields",
    "fact",
    "fail_code_run",
    "fail_run",
    "finish_code_run",
    "graph_router",
    "has_never_verb",
    "install_fake_responses",
    "install_fake_reviews",
    "knowledge_context",
    "knowledge_router",
    "last_completed_run",
    "last_completed_run_at",
    "live_override",
    "load_agent_context",
    "load_run_v2_context",
    "match",
    "match_intake",
    "notice_context",
    "open_capability_run",
    "open_deterministic_run",
    "open_plan_child_run",
    "open_turn_run",
    "override_rate",
    "pending_suggestion",
    "pending_suggestions",
    "proposal_approver",
    "recommend",
    "record_code_run",
    "record_synthetic_run",
    "register_change_set_applier",
    "register_decision_source",
    "register_engagement_run_agent",
    "register_mode_mapping",
    "register_mode_plan",
    "register_mode_preparer",
    "register_notice_shadows",
    "register_proposal_adapter",
    "register_section_source",
    "register_session_links",
    "register_session_subject",
    "register_suggestion_applier",
    "register_suggestion_target",
    "register_threshold_policy",
    "registry_problems",
    "request_review",
    "reserved_plan_tools",
    "review",
    "review_citation_states",
    "review_sha256",
    "router",
    "run_initiators",
    "run_log_count",
    "run_outcome",
    "run_record_hashes",
    "run_session_turn",
    "run_v2_status",
    "run_workflow_id",
    "screen",
    "screening_responder",
    "screening_results_for",
    "search_knowledge",
    "shadow_score",
    "spec",
    "spec_problems",
    "spec_v2",
    "stage_for",
    "start_agents",
    "start_screening",
    "start_section_draft",
    "starts_in_shadow",
    "subject_engagement",
    "template_drafts_router",
    "text_part",
    "tool_output_for_model",
    "txt",
    "upload_review_available",
    "verify_citations",
    "workflow_id",
]

# S29 leftovers (TASK-6012): what the replay recorders and the OCR suite runner read (BOUND-001).
from abacus.modules.agents.knowledge_workflow import (  # noqa: E402
    KnowledgeEmbeddingWorkflow as KnowledgeEmbeddingWorkflow,
)

# P-10-T27 (DEC-3117): the agents topics of the invalidation stream.
from abacus.modules.agents.realtime_topics import register as _register_topics  # noqa: E402
from abacus.modules.agents.workflow_types import BatchOutcome as BatchOutcome  # noqa: E402
from abacus.modules.agents.workflow_types import (  # noqa: E402
    FailKnowledgeInput as FailKnowledgeInput,
)
from abacus.modules.agents.workflow_types import KnowledgeInput as KnowledgeInput  # noqa: E402

_register_topics()
