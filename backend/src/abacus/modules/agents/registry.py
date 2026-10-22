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
        "guidance_drafts",  # SPEC-035 (TASK-072)
        "guidance_draft_decisions",  # SPEC-035 (TASK-073)
        "template_guidance_drafts",  # SPEC-035 Q3 (TASK-074)
        "entry_assessments",  # SPEC-037 Q4 (TASK-085)
        "agent_stages",  # SPEC-036 (TASK-076): owner-written, app reads only
        "template_guidance_decisions",  # SPEC-035 Q3 (TASK-074)
        "inbox_match_proposals",
        "follow_up_schedules",  # SPEC-027 (TASK-051); renamed by F-03-T16
        "follow_up_items",
        "agent_runs",
        "screening_results",
        "knowledge_documents",  # SPEC-009 Q5
        "knowledge_chunks",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "agent_activity",  # SPEC-027 (TASK-050): the feed is never rewritten
        "upload_reviews",  # SPEC-030 (TASK-058): proposals, as made
        "upload_review_flags",  # SPEC-030 (TASK-058): proposals, as made
        "inbox_match_runs",  # SPEC-033 (TASK-065): proposals, as made
        "guidance_drafts",  # SPEC-035 (TASK-072): proposals, as made
        "guidance_draft_decisions",  # SPEC-035 (TASK-073): people's decisions, as made
        "template_guidance_drafts",  # SPEC-035 Q3 (TASK-074)
        "entry_assessments",  # SPEC-037 Q4 (TASK-085): proposals, as made
        "template_guidance_decisions",  # SPEC-035 Q3 (TASK-074)
        "inbox_match_proposals",  # SPEC-033 (TASK-065): proposals, as made
        "follow_up_items",  # SPEC-027 (TASK-051)
        "screening_results",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
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
    # SPEC-027 (TASK-050): an engagement's agent paused or resumed.
    "engagement_agents": frozenset(
        {"paused_at", "paused_by", "reason", "updated_at", "self_paused_reason"}
    ),
    # SPEC-028 (TASK-052): an import's scan result and what became of it.
    # SPEC-027 (TASK-051): a drafted reminder is sent or dismissed by a person.
    "follow_up_schedules": frozenset({"status", "note", "decided_by", "decided_at"}),
    "agent_runs": frozenset(
        {"status", "context_hash", "output", "failure_code", "finished_at"}
        | {"queued_reason", "estimated_start_at"}
    ),
    # SPEC-009: document status, and each chunk's vector written once.
    "knowledge_documents": frozenset({"status", "failure_code", "withdrawn_at"}),
    "knowledge_chunks": frozenset({"embedding", "embedding_model", "embedded_at"}),
}
