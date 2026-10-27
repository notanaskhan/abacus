"""The agents module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "engagement_agents",  # SPEC-027 (TASK-050)
        "agent_activity",
        "upload_reviews",  # SPEC-030 (TASK-058)
        "upload_review_flags",
        "inbox_match_runs",  # SPEC-033 (TASK-065)
        "inbox_match_decisions",  # P-04-T25 review M6 (migration 0232): a person's rejection
        "guidance_drafts",  # SPEC-035 (TASK-072)
        "guidance_draft_decisions",  # SPEC-035 (TASK-073)
        "template_guidance_drafts",  # SPEC-035 Q3 (TASK-074)
        "entry_assessments",  # SPEC-037 Q4 (TASK-085)
        "agent_stages",  # SPEC-036 (TASK-076): owner-written, app reads only
        "template_guidance_decisions",  # SPEC-035 Q3 (TASK-074)
        "inbox_match_proposals",
        "follow_up_schedules",  # SPEC-027 (TASK-051); renamed by F-03-T16
        "follow_up_items",
        "follow_up_returns",  # P-06-T14 (migration 0121)
        "agent_runs",
        "screening_results",
        "screening_feedback",  # P-06-T20 (migration 0154): SHL-20 f
        "screening_rerun_requests",  # P-06-T20 security review: reruns, rate-limited per item
        "knowledge_documents",  # SPEC-009 Q5
        "knowledge_chunks",
        # P-04-T05 (migration 0095, ADR-161): suggestions and proposals with their decisions.
        "suggestions",
        "suggestion_decisions",
        "proposals",
        "proposal_rows",
        "proposal_decisions",
        "agent_run_records",  # Q-02-T41 (0171, ADR-169 §3): one per ended specialist run
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "agent_activity",  # SPEC-027 (TASK-050): the feed is never rewritten
        "upload_reviews",  # SPEC-030 (TASK-058): proposals, as made
        "upload_review_flags",  # SPEC-030 (TASK-058): proposals, as made
        "inbox_match_runs",  # SPEC-033 (TASK-065): proposals, as made
        "inbox_match_decisions",  # P-04-T25 review M6 (migration 0232)
        "guidance_drafts",  # SPEC-035 (TASK-072): proposals, as made
        "guidance_draft_decisions",  # SPEC-035 (TASK-073): people's decisions, as made
        "template_guidance_drafts",  # SPEC-035 Q3 (TASK-074)
        "entry_assessments",  # SPEC-037 Q4 (TASK-085): proposals, as made
        "template_guidance_decisions",  # SPEC-035 Q3 (TASK-074)
        "inbox_match_proposals",  # SPEC-033 (TASK-065): proposals, as made
        "follow_up_items",  # SPEC-027 (TASK-051)
        "follow_up_returns",  # P-06-T14: the files a screening return named, as sent
        "screening_results",  # P-06-T20: aggregates supersede, never update (0154)
        "screening_feedback",  # P-06-T20: a person's feedback, as given
        "screening_rerun_requests",  # P-06-T20: a person's rerun, as asked
        "suggestion_decisions",  # P-04-T05
        "proposal_rows",
        "proposal_decisions",
        "agent_run_records",  # Q-02-T41: written once at completion, never rewritten
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # Run records (Q-02-T41, migration 0171): everything but `persisted_at`.
    "agent_run_records": frozenset(
        {"run_id", "tenant_id", "engagement_id", "work_item_id", "capability", "spec_version"}
        | {"stage", "prompt_ref", "prompt_sha256", "model", "route", "region", "terms_version"}
        | {"boundary_basis", "input_hashes", "records_read", "citations", "outcome"}
        | {"initiator_user_id", "started_at", "completed_at", "record_sha256"}
    ),
    # Follow-ups v2 (P-06-T14, migration 0121).
    "follow_up_schedules": frozenset(
        {"tenant_id", "engagement_id", "recipient_user_id", "status", "note", "agent_run_id"}
        | {"binder_id", "recipient_contact_id", "kind", "template_key", "body_fingerprint"}
        | {"drafted_by_kind"}
    ),
    "follow_up_returns": frozenset(
        {"tenant_id", "follow_up_id", "evidence_version_id", "reason_code"}
    ),
    # P-04-T05 (migration 0095)
    "suggestions": frozenset(
        {"tenant_id", "engagement_id", "target_type", "target_id", "field_key", "proposed_value"}
        | {"rationale_ref", "citation_ids", "confidence", "agent_run_id", "proposal_id"}
    ),
    "suggestion_decisions": frozenset(
        {"tenant_id", "suggestion_id", "decision", "edited_value", "citation_note_sealed"}
        | {"reason_code", "undoes_decision_id", "decided_by"}
        | {"id"}  # P-04-T24 (migration 0230): a sealed note is bound to its row
    ),
    "proposals": frozenset(
        {"tenant_id", "engagement_id", "kind", "title", "reasoning_ref", "policy_eval"}
        | {"routed_to_user_id", "set_ref", "checkpoint_id", "agent_run_id"}
    ),
    "proposal_rows": frozenset(
        {"tenant_id", "proposal_id", "n", "suggestion_id", "field_ref", "label", "before"}
        | {"after", "cause", "citation_ids", "unsupported"}
    ),
    "proposal_decisions": frozenset(
        {"tenant_id", "proposal_id", "decision", "reason_code", "note_sealed", "edits"}
        | {"seen_version", "routed_to_user_id", "undoes_decision_id", "approval_grant_id"}
        | {"decided_by"}
        | {"id"}  # P-04-T24 (migration 0230): a sealed note is bound to its row
    ),
    # P-04-T25 security review M6 (migration 0232): a person's rejection of a match.
    "inbox_match_decisions": frozenset(
        {"id", "tenant_id", "match_id", "decision", "reason_code", "note_sealed", "decided_by"}
    ),
    # Inbox match proposals (SPEC-033; TASK-065): the matcher's, as made.
    "inbox_match_runs": frozenset(
        {"id", "tenant_id", "engagement_id", "inbox_file_id", "agent_run_id", "prompt_ref"}
        | {"none_fit", "truncated"}
    ),
    # Guidance drafts (SPEC-035; TASK-072): the drafter's, as made.
    "guidance_drafts": frozenset(
        {"tenant_id", "engagement_id", "request_item_id", "agent_run_id", "prompt_ref", "why"}
        | {"good_looks_like", "effort", "effort_reason", "blocks_fieldwork", "blocks_reason"}
        | {"passed_checks", "check_reasons"}
    ),
    "guidance_draft_decisions": frozenset(  # SPEC-035 (TASK-073)
        {"tenant_id", "draft_id", "decision", "edited", "confirmed_read", "decided_by"}
    ),
    # Drafted guidance on templates (SPEC-035 Q3; TASK-074): drafts and decisions, as made.
    "template_guidance_drafts": frozenset(
        {"tenant_id", "methodology_version_id", "position", "agent_run_id", "prompt_ref", "why"}
        | {"good_looks_like", "effort", "effort_reason", "blocks_fieldwork", "blocks_reason"}
        | {"passed_checks", "check_reasons"}
    ),
    # The entry assessor (SPEC-037 Q4; TASK-085): proposals, as made.
    "entry_assessments": frozenset(
        {"tenant_id", "engagement_id", "selected_item_id", "agent_run_id", "prompt_ref"}
        | {"verdict", "shown_verdict", "rationale", "citations"}
    ),
    "template_guidance_decisions": frozenset(
        {"tenant_id", "draft_id", "decision", "why", "good_looks_like", "effort"}
        | {"blocks_fieldwork", "edited", "confirmed_read", "decided_by"}
    ),
    "inbox_match_proposals": frozenset(
        {"tenant_id", "match_id", "rank", "request_item_id", "confidence", "rationale"}
        | {"citations", "shown"}
    ),
    "agent_runs": frozenset(
        {"id", "tenant_id", "agent_id", "spec_version", "engagement_id", "task_scope"}
        | {"evidence_version_id", "initiator_user_id", "source_event_id"}
        | {"inbox_file_id"}  # SPEC-033 (TASK-066): the matcher's file
        | {"methodology_version_id"}  # SPEC-035 Q3 (TASK-074): a firm-level run's version
        | {"shadow"}  # SPEC-036 (TASK-076): started in shadow
    ),
    "screening_results": frozenset(
        {"id", "tenant_id", "engagement_id", "evidence_version_id", "agent_run_id"}
        | {"action", "confidence", "rationale", "citations", "unverified"}
        # P-06-T20 (0154): the request-batch aggregate; its author is set by the database.
        | {"subject_kind", "request_item_id", "batch_no", "verdict"}
        | {"source_result_ids", "source_review_ids", "evidence_version_ids", "checks"}
        | {"file_flags", "supersedes_id"}
    ),
    "screening_feedback": frozenset(
        {"id", "tenant_id", "engagement_id", "screening_result_id", "user_id", "thumb"}
        | {"reason_code", "note_sealed"}
    ),
    "screening_rerun_requests": frozenset(
        {"tenant_id", "engagement_id", "request_item_id", "requested_by", "files"}
    ),
    # Knowledge (SPEC-009): vectors and status are set later by the embedding workflow.
    "knowledge_documents": frozenset(
        {"id", "tenant_id", "title", "source_kind", "media_type", "fingerprint", "char_count"}
        | {"added_by"}
    ),
    "knowledge_chunks": frozenset(
        {"tenant_id", "document_id", "position", "heading_path", "text", "char_count"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "suggestions": frozenset({"status", "version"}),  # P-04-T05
    "proposals": frozenset({"state", "routed_to_user_id", "version"}),  # P-04-T05
    # SPEC-027 (TASK-050): an engagement's agent paused or resumed.
    "engagement_agents": frozenset(
        {"paused_at", "paused_by", "reason", "updated_at", "self_paused_reason"}
    ),
    # SPEC-028 (TASK-052): an import's scan result and what became of it.
    # SPEC-027 (TASK-051): a drafted reminder is sent or dismissed by a person.
    # P-06-T14: edited, sent (with its Undo window) or undone by a person.
    "follow_up_schedules": frozenset(
        {"status", "note", "decided_by", "decided_at", "body_sealed", "edit_fingerprint"}
        | {"sent_by", "sent_at", "not_before", "undone_at"}
    ),
    "agent_runs": frozenset(
        {"status", "context_hash", "output", "failure_code", "finished_at"}
        | {"queued_reason", "estimated_start_at"}
    ),
    # SPEC-009: document status, and each chunk's vector written once.
    "knowledge_documents": frozenset({"status", "failure_code", "withdrawn_at"}),
    "knowledge_chunks": frozenset({"embedding", "embedding_model", "embedded_at"}),
}
