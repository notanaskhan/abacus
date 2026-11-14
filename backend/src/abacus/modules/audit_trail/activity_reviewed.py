"""The reviewed fallback list (G-02-T08): audited actions that render through the activity
catalogue's generic fallback (`activity_catalogue.fallback`), reviewed on 2026-10-26.

The static check holds every `record("...")` literal to a catalogue entry, a module's registered
entry or this list. Adding an action here is a review that the fallback's category and marker
read right for it; give it a catalogue entry instead when they do not.
"""

from __future__ import annotations

from typing import Final

REVIEWED_FALLBACK: Final = frozenset(
    {
        # reviewed 2026-11-14 (S43): I-02-T14 a Today question, identifiers only (DEC-60)
        "today_brief.question_asked",
        # reviewed 2026-11-14 (S43): W-02-T20 an artifact download and a session drill
        "run_artifact.downloaded",
        "session.drill_appended",
        # reviewed 2026-11-12 (S37): T-04-T36 K-1 activities and treatments
        "pass_through_activity.created",
        "pass_through_activity.released",
        "pass_through_activity.saly_refreshed",
        "pass_through_treatment.approved",
        "pass_through_treatment.overridden",
        # reviewed 2026-11-12 (S37): P-10-T44 frozen traces and the run_events prune
        "agent_run.trace_frozen",
        "run_events.pruned",
        # reviewed 2026-11-12 (S37): P-10-T43 workbench sessions and their turns
        "agent_run.turn_recorded",
        "session.created",
        "session.message_posted",
        "session.turn_recorded",
        # reviewed 2026-11-11 (S35 round 2): A-07-T41 AUD-23's report date and city
        "audit_report.date_set",
        # reviewed 2026-11-10 (S35): A-07-T42 post-lock additions and seal verification
        "archive.addition_logged",
        "archive.seal_mismatch",
        "archive.seal_verified",
        "archive_addition.created",
        "archive_addition.decided",
        # reviewed 2026-11-10 (S35): P-10-T36 the synthetic recorder's later step states
        "agent_run.advanced_synthetic",
        # reviewed 2026-11-10 (S35): P-10-T33 a person's run commands (agents/commands.py)
        "agent_feedback.created",
        "agent_run.plan_approved",
        "agent_run.plan_cancelled",
        "agent_run.plan_edited",
        "agent_run.question_answered",
        "agent_run.question_skipped",
        "agent_run.redirected",
        "agent_run.signed_off",
        "agent_run.stop_requested",
        # reviewed 2026-11-10 (S35): P-10-T32 AgentRunWorkflow part 2's waits, retries and stop
        "agent_run.decision_raised",
        "agent_run.question_opened",
        "agent_run.retried",
        "agent_run.skip_default_applied",
        "agent_run.stopped",
        "agent_run_step.retry_requested",
        # reviewed 2026-11-10 (S34): T-04-T17 document approvals and the final-approval request
        "document.approval_reversed",
        "document.approved",
        "tax_return.final_approval_requested",
        # reviewed 2026-11-10 (S34): T-04-T15 the workspace in the review grammar
        "return_field.edited",
        "return_field.proposal_applied",
        "tax_proposal.linked",
        # reviewed 2026-11-10 (S34): A-07-T37 the lock decision, the seal, the engagement archived
        "archive.engagement_archived",
        "archive.lock_decided",
        "archive.sealed",
        # reviewed 2026-11-10 (S34): A-07-T36 filings and post-release clocks
        "archive.deadline_risk",
        "filing.opened",
        "governance_communication.due_set",
        "filing.updated",
        # reviewed 2026-11-11 (S36): T-04-T28 the synthetic scenario seeded a return worksheet
        "return_worksheet.seeded",
        # reviewed 2026-11-11 (S36): P-10-T39 a person turned an engagement's Auto mode on or off
        "engagement_ai.auto_mode_set",
        # reviewed 2026-11-11 (S36): P-10-T42 the ledger posted a completed run's minutes
        "agent_minutes.posted",
        # reviewed 2026-11-11 (S36): P-10-T38 a run's workbook, its Save to Files proposal, the
        # approved write's outcome on the run's stream and the filed copy ("via Agent")
        "run_artifact.created",
        "agent_run.write_proposed",
        "agent_run.writes_counted",
        "agent_run.write_saved",
        "agent_run.write_undone",
        "agent_run.write_failed",
        "file.saved",
        # reviewed 2026-11-10 (S34): P-10-T29 AgentRunWorkflow part 1's transitions
        "agent_run.finished",
        "agent_run.plan_proposed",
        "agent_run.plan_refused",
        "agent_run.state_changed",
        "agent_run_step.finished",
        "agent_run_step.started",
        # reviewed 2026-11-10 (S34): P-05-T05/T06 collaboration; AUD-29 shows only
        # `todo.deleted` and `comment.redacted` (OQ-4, P-05-T11's catalogue entries)
        "comment.corrected",
        "comment_thread.muted",
        "comment_thread.opened",
        "comment_thread.reopened",
        "comment_thread.resolved",
        "comment_thread.shared",
        "comment_thread.unmuted",
        "comment_thread.converted",
        "todo.assigned",
        "todo.checklist_changed",
        "todo.completed",
        "todo.created",
        "todo.deleted",
        "todo.moved",
        "todo.reopened",
        "todo.seen",
        "todo.updated",
        # reviewed 2026-11-09 (S33 end pass): A-07-T30/T31/T32, P-10-T27, R-02-T15
        "agent_run.code_recorded",
        "archive.assembly_started",
        "archive.binder_index_built",
        "archive.lock_requested",
        "realtime.invalidated",
        "report.final_render_requested",
        "report.release_failed",
        "report.release_replayed",
        "report.release_requested",
        "uncorrected_misstatements.acknowledged",
        "acceptance.answers_updated",
        "acceptance.condition_completed",
        "acceptance.decided",
        "acceptance.flag_added",
        "acceptance.manual_check_completed",
        "acceptance.manual_check_requested",
        "acceptance.record_opened",
        "acceptance.review_completed",
        "acceptance.review_requested",
        "acceptance.sent_to_partner",
        "account_mapping.edited",
        "action_cap.refused",
        "adjustment.proposed",
        "agent.activity",
        "agent.digest",
        "agent_run.escalated",
        "agent_run.failed",
        "agent_run.started",
        "agent_run.trace_exported",
        "agent_stage.changed",  # Q-02-T06 (ED-120): a platform staff change of a firm's stage
        "ai.boundary_refused",
        "answer_effect.recorded",  # reviewed 2026-11-05 (S26, S27)
        "approval_grant.consumed",
        "approval_grant.voided",
        "archive.locked",
        "assurance.archive_recorded",  # A-01-T23: export id, manifest digest, never the ref
        "assurance.phase_derived",
        "assurance.phase_recorded",
        "assurance.profile_updated",
        "assurance.release_recorded",  # A-01-T23: the recorded date and kind, as numbers
        "attribute_result.marked",  # reviewed 2026-11-05 (S26, S27)
        "attribute_result.recorded",  # reviewed 2026-11-05 (S26, S27)
        "attribute_test.created",  # reviewed 2026-11-05 (S26, S27)
        "audit_chain.anchored",
        "auth.sign_in_refused",
        "autonomy_policy.updated",
        "binder.closed",
        "binder.created",
        "binder.duplicated",
        "binder.mark_done_undone",
        "binder.marked_done",
        "binder.publish_undone",
        "binder.published",
        "binder.recipients_changed",
        "binder.unpublished",
        "budget.anomaly",
        "budget.soft_crossed",
        "budget.updated",
        "citation.created",
        "citation.relinked",
        "client.created",
        "client.record_changed",
        "client.updated",
        "client_access.granted",
        "client_access.revoked",
        "client_data.gate_refused",
        "client_entity.attributes_changed",
        "client_entity.created",
        "client_entity.updated",
        # P-07-T52: the bulk import (identifiers, codes and counts only)
        "client_import.completed",
        "client_import.failed",
        "client_import.files_erased",
        "client_import.row_applied",
        "client_import.row_decided",
        "client_import.row_failed",
        "client_import.row_skipped",
        "client_import.started",
        "client_import.uploaded",
        "client_intake.committed",
        "client_intake.discarded",
        "client_intake.saved",
        "client_intake.started",
        "client_invitation.accept_attempted",
        "client_invitation.accept_refused",
        "client_invitation.accepted",
        "client_invitation.created",
        "client_invitation.expiry_notified",  # P-07-T47: the expiry only, never the address
        "client_invitation.renewed",
        "client_invitation.resent",
        "client_invitation.revoked",
        "client_invitation.token_issued",
        "client_item.responded",
        "client_item.response_withdrawn",
        "client_list.marked_done",
        "client_member.removed",
        "comment.posted",
        "comment.redacted",
        "comment_thread.read",
        "conflict.cleared",
        "control_activity.recorded",  # reviewed 2026-11-05 (S26, S27)
        "control_exception.recorded",  # reviewed 2026-11-05 (S26, S27)
        "control_exception.routed",  # reviewed 2026-11-05 (S26, S27)
        "control_exception.severity_proposed",  # reviewed 2026-11-05 (S26, S27)
        "decision.refused_non_human",  # K-01-T06: an agent or the platform asked to approve
        "ebp_late_remittance.correction_recorded",  # reviewed 2026-11-05 (S26, S27)
        "envelope.imported",  # N-02-T08: record-mode import (SIG-01 r)
        "envelope.provider_hint",  # N-02-T19: a verified Connect hint (duplicate flag only)
        "envelope.provider_unavailable",  # N-02-T18: kill switch, W7 or install off; not sent
        "envelope_import_file.staged",  # N-02-T08: a scanned file for an import
        "extension_payment.approved",  # reviewed 2026-11-05 (S26, S27)
        "filing_extension.ack_unmatched",  # reviewed 2026-11-05 (S26, S27)
        "filing_extension.acknowledged",  # reviewed 2026-11-05 (S26, S27)
        "filing_extension.filed_recorded",  # reviewed 2026-11-05 (S26, S27)
        "filing_extension.flagged",  # reviewed 2026-11-05 (S26, S27)
        "human_gate.reassigned",  # I-01-T07: a person moved a gate to someone else (user ids)
        "conflict_check.run",
        "connection.checked",
        "connection.created",
        "connection.failed",
        "connection.revoked",
        "connection.started",
        "connection.state_refused",
        "connection.state_used",
        "contact.access_changed",
        "contact.created",
        "contact.invited",
        "contact.portal_activated",
        "contact.unlocked",
        "contact.updated",
        "decision.analysis_requested",
        "decision.decided",
        "decision.notified",
        "decision.reassessed",
        "decision_card.raised",
        "decision_card.superseded",
        "document.classified",  # N-01-T17: a rule classification (ids and a page count)
        "email_template.draft_discarded",  # R-01-T19
        "email_template.draft_saved",  # R-01-T19
        "email_template.imported",  # R-01-T23
        "email_template.published",  # R-01-T19
        "email_template.test_sent",  # R-01-T23
        "engagement.acceptance_file_attached",
        "engagement.acceptance_recorded",
        "engagement.ai_excluded",
        "engagement.ai_included",
        "engagement.created",
        "engagement.letter_file_attached",
        "engagement.letter_recorded",
        "engagement.rolled_forward",
        "engagement_agent.paused",
        "engagement_agent.resumed",
        "engagement_agent.self_paused",
        "engagement_agent.self_resumed",
        "engagement_contact.designated",
        "engagement_draft.discarded",
        "engagement_draft.saved",
        "engagement_draft.started",
        "engagement_draft.started_acceptance",
        "engagement_export.downloaded",  # A-01-T22: bytes and range, never content
        "engagement_export.expired",  # A-01-T22: the 7 days (system)
        "engagement_export.failed",
        "engagement_export.packaged",
        "engagement_export.requested",
        "engagement_export.snapshotted",
        "engagement_export.started",
        "engagement_export.undone",
        "engagement_export.voided",  # A-01-T22 (P-31): withdrawn content (system)
        "engagement_member.added",
        "engagement_member.hours_changed",
        "engagement_member.removed",
        "engagement_member.role_changed",
        "engagement_member.self_joined",
        "entity_relationship.created",
        "entry_assessment.created",
        "entry_assessment.requested",
        "eqr.assigned",
        "eqr.concurred",
        "eqr.eligibility_approved",
        "evidence.uploaded",
        "evidence_item.created",
        "evidence_version.created",
        "evidence_version.flagged",
        "evidence_version.read",
        "evidence_version.withdrawal_refused",
        "evidence_version.withdrawn",
        "evidence_withdrawal.erase_blocked",
        "evidence_withdrawal.erased",
        "fieldwork.accounts_confirmed",
        "fieldwork.settings_changed",
        "finding.communicated",
        "finding.raised",
        "finding.severity_",
        "firm.agents_paused",
        "firm.agents_resumed",
        "firm.ai_client_data_off",
        "firm.ai_client_data_on",
        "firm.created",
        "firm.demo_clock_changed",
        "firm.drafted_guidance_setting_changed",
        "firm.letter_policy_changed",
        "firm.signup_attempted",
        "firm.time_zone_changed",
        "firm_integration.connected",  # TASK-2152: a firm's DocuSeal install (ADR-342)
        "firm_integration.disconnected",
        "firm_policy_override.set",
        "firm_setting.provisioned",
        "firm_setting.set",
        "firm_setting.updated",
        # K-02-T08: a firm standard's lifecycle (identifiers, versions and dates only)
        "firm_standard.created",
        "firm_standard.owner_changed",
        "firm_standard_version.discarded",
        "firm_standard_version.drafted",
        "firm_standard_version.edited",
        "firm_standard_version.published",
        "follow_up.dismissed",
        "follow_up.drafted",
        "follow_up.edited",
        "follow_up.limit_reached",  # R-01-T24
        "follow_up.scheduled_sent",  # R-01-T24 (DEC-74): the system's scheduled Reminder
        "follow_up.sent",
        "follow_up.undone",
        "follow_up_policy.saved",  # R-01-T24
        "fulfilment.created",
        "fulfilment.voided",
        "fulfilment.withdrawn",
        "gl_import.duplicate",
        "gl_import.received",
        "gl_import.refused",
        "gl_import.rendered",
        "gl_snapshot.created",
        "grouping_set.imported",
        "grouping_set.published",
        "guidance_draft.approved",
        "guidance_draft.created",
        "guidance_draft.discarded",
        "guidance_draft.requested",
        "home_activity.projected",  # I-01-T12 (DEC-900): one activity row, the code only
        "home_activity.pruned",  # I-01-T12: a count of rows past 90 days
        "human_gate.projected",
        "inbound_message.recorded",  # N-01-T09: a message reached the inbox
        "inbox_attachment.flagged",  # N-01-T17: one code-flag run (ids and a count)
        "inbox_attachment.received",  # N-01-T09: a scanned, stored file
        "inbox_file.added",
        "inbox_file.assigned",
        "inbox_file.discarded",
        "inbox_file.duplicate_flagged",
        "inbox_file.flagged",
        "inbox_match.created",
        "inbox_match.requested",
        "inbox_thread.created",  # N-01-T09: a new inbox thread
        "incident.propagated",
        "incident.recorded",
        "independence.annual_",
        "independence.concluded",
        "independence.confirmed",
        "independence.declined",
        "independence.reminded",
        "independence.requested",
        "independence.statement_published",
        "independence_breach.logged",
        "independence_breach.updated",
        "integration_secret.erased",
        "integration_secret.stored",
        "invitation.resent",
        "invitation.revoked",
        "issue.fix_instructions_set",  # P-04-T31
        "issue.marked_not_applicable",  # P-04-T31
        "issue.reopened",  # P-04-T31
        "issue.resolved",  # P-04-T31
        "issue.sent_to_client",  # P-04-T31
        "issue.verified",  # P-04-T31
        "item.signed",
        "knowledge_chunk.embedded",
        "knowledge_document.added",
        "knowledge_document.failed",
        "knowledge_document.ready",
        "knowledge_document.withdrawn",
        "ledger.pull_requested",  # A-02-T30: an on-demand pull
        "ledger_import.duplicate",
        "ledger_import.failed",
        "ledger_import.received",
        "ledger_import.refused",
        "ledger_snapshot.created",
        "legal_hold.applied",
        "legal_hold.counted",
        "legal_hold.inherited",
        "legal_hold.lifted",
        "legal_hold.placed",
        "legal_hold.released",
        "letter.recorded",
        "mapping_set.created",
        "mapping_set.version_followed",  # A-03-T14: the set followed a TB version, 2026-11-01
        "materiality.decided",
        "materiality.set",
        "membership.access_ending_notified",
        "membership.attributes_changed",
        "membership.deactivated",
        "membership.profile_set",
        "membership.revoked",
        "membership.role_changed",
        "membership.security_role_changed",
        "message.blocked",
        "message.sent",
        "methodology.applied",
        "methodology.imported",
        "methodology.published",
        "misstatement.recorded",
        "model.called",
        "nas.evaluated",
        "notice.analysis_recorded",  # reviewed 2026-11-05 (S26, S27)
        "notice.created",  # reviewed 2026-11-05 (S26, S27)
        "notice.note_added",  # reviewed 2026-11-05 (S26, S27)
        "notice.proposed_items_recorded",  # reviewed 2026-11-05 (S26, S27)
        "notice.return_as_filed_recorded",  # reviewed 2026-11-05 (S26, S27)
        "notice.status_changed",  # reviewed 2026-11-05 (S26, S27)
        "deficiency.severity_proposed",  # reviewed 2026-11-08 (A-06-T16)
        "deficiency.severity_suggested",  # reviewed 2026-11-08 (A-06-T16)
        "notice_intake.attached",  # reviewed 2026-11-06 (N-04-T07)
        "notice_intake.created",  # reviewed 2026-11-05 (S26, S27)
        "notice_intake.discarded",  # reviewed 2026-11-05 (S26, S27)
        "notice_intake.extracted",  # reviewed 2026-11-06 (N-04-T07)
        "notice_intake.updated",  # reviewed 2026-11-05 (S26, S27)
        "notice_response.drafted",  # reviewed 2026-11-05 (S26, S27)
        "notice_response.edited",  # reviewed 2026-11-05 (S26, S27)
        "notice_response.regenerated",  # reviewed 2026-11-05 (S26, S27)
        "notification.created",
        "notification.read",
        "notification.read_all",
        "notification_preference.changed",
        # K-01-T06: a methodology version's lifecycle (identifiers and dates only)
        "methodology_version.approve_refused",
        "methodology_version.approved",
        "methodology_version.submitted",
        "methodology_version.superseded",
        # R-01-T26: ADM-10's settings and the read-only preview (versions and ids only)
        "pilot_metrics.computed",  # Q-04-T008: a week's pilot snapshots
        "portal.preview_viewed",
        "portal_settings.draft_discarded",
        "portal_settings.draft_saved",
        "portal_settings.published",
        "notifications.purged",
        "office.created",
        "office.updated",
        "onboarding.acknowledged",
        "pii.reveal_throttled",
        "pii.revealed",
        "portal.drop_received",
        "portal.drop_sort_exists",
        "portal.drop_sorted",
        "portal.drop_unsorted",
        "portal_branding.updated",
        "portal_device.revoked",
        "portal_domain.activated",
        "portal_domain.added",
        "portal_mfa.reset",
        "portal_preferences.updated",
        "portal_sign_in.code_requested",
        "procedure.concluded",
        "procedure.failed",
        "procedure.parameters_changed",
        "procedure.picks_added",
        "procedure.result_recorded",
        "procedure.selected",
        "procedure.selection_requested",
        "procedure.started",
        "procedure.support_requested",
        "procedure_session.plan_approved",
        "questionnaire.edited",  # reviewed 2026-11-05 (S26, S27)
        "report.released",
        "representation.added",
        "representation.removed",
        "request_item.client_assigned",
        "request_item.client_visibility_changed",
        "request_item.created",
        "request_item.created_by_answer_effect",  # reviewed 2026-11-05 (S26, S27)
        "request_item.delegated",
        "request_item.delegation_ended",
        "request_item.deleted",
        "request_item.document_kind_set",
        "request_item.drafted_guidance_applied",
        "request_item.due_date_set",
        "request_item.guidance_set",
        "request_item.ignore_note_added",
        "request_item.ignore_undone",
        "request_item.ignored",
        "request_item.incorporated",
        "request_item.returned_to_client",
        "request_item.rule_link_voided",
        "request_item.send_undone",
        "request_item.sent",
        "request_item.updated",
        "request_item.upload_withdrawn",
        "request_item.uploaded",
        "request_item.waived",
        "request_list.created",
        "request_list.default_due_date_set",
        "request_list.imported",
        "retention.extended",
        "retention_policy.defaults_applied",
        "retention_policy.updated",
        "review.assigned",
        "review.released",
        "review.taken",
        "review_decision.created",
        "review_decision.undone",
        "review_note.cleared",
        "review_note.raised",
        "review_note.reopened",
        "review_note.responded",
        "review_note.withdrawn",
        "risk.approved",
        "risk.recorded",
        "roll_forward_draft.created",  # P-07-T55: ENG-13's draft, its source and period
        "roll_forward_draft.discarded",  # P-07-T55
        "roll_forward_draft.saved",  # P-07-T55
        "sample.approved",
        "screening.completed",
        "screening.feedback_sent",
        "screening.recorded",
        "screening.requested",
        "screening.rerun_requested",
        "screening_result.created",
        "screening_result.read",
        "secure_link.issued",
        "secure_link.renewed",
        "secure_link.revoked",
        "secure_link.token_issued",
        "service_line_policy.updated",
        "session.ended",
        "sign_off.re_review_requested",  # reviewed 2026-11-05 (S26, S27)
        "sign_off.recorded",
        "sign_off.went_stale",
        "soc_report.bridge_letter_drafted",  # reviewed 2026-11-05 (S26, S27)
        "soc_report.cuec_mapped",  # reviewed 2026-11-05 (S26, S27)
        "soc_report.evaluated",  # reviewed 2026-11-05 (S26, S27)
        "soc_report.reliance_requested",  # reviewed 2026-11-05 (S26, S27)
        "staff_invitation.accept_attempted",
        "staff_invitation.accepted",
        "staff_invitation.created",
        "staff_invitation.issued",
        "staff_invitation.none_issued",
        "staff_invitation.resent",
        "staff_invitation.revoked",
        "staff_invitation.token_issued",
        "statement.approved",
        "support.request",
        "support_session.emergency_approved",
        "support_session.ended",
        "support_session.expired",
        "support_session.requested",
        "support_session.revoked",  # G-02-T14: turning support off closes pending requests
        "sync_run.failed",
        "sync_run.raw_stored",
        "sync_run.requested_again",
        "sync_run.snapshot_linked",
        "sync_run.started",
        "sync_run.succeeded",
        "team.approved",
        "team.created",
        "team.member_added",
        "team.member_removed",
        "team.portal_visibility_changed",
        "team.updated",
        "tax_return.due_dates_pinned",  # T-02-T10: dates as integers, the rule count
        "threshold_policy.created",
        "threshold_policy.owner_changed",
        "threshold_policy_version.discarded",
        "threshold_policy_version.drafted",
        "threshold_policy_version.edited",
        "threshold_policy_version.published",
        "tenant.entitlements_changed",
        "tenant.provisioned",
        "tenant_key.recorded",
        "third_party.upload_noticed",
        "tie_out_check.defined",
        "tie_out_check.updated",  # ED-176: C9 §7's name for an edit (was `.changed`)
        "tin.reveal_throttled",
        "tin.revealed",
        "trial_balance.annotated",
        "trial_balance.created",
        "trial_balance.version_adopted",
        "upload.checked",
        "upload.extracted",
        "upload.extraction_exists",
        "upload.masked_preview_exists",
        "upload.masked_previewed",
        "upload.pii_scan_exists",
        "upload.pii_scanned",
        "upload.preview_exists",
        "upload.previewed",
        "evidence_version.ocr_retry_requested",
        "upload.refused",
        "upload.words_exist",
        "upload.words_extracted",
        "upload_intent.announced",
        "upload_review.created",
        "upload_review.requested",
        "user_preference.updated",
        "wall.approved",
        "wall.removed",
        "work_item.assigned",
        "work_item.created",
        "work_item.unassigned",
        "workpaper.cells_edited",  # A-04-T04 (DEC-1762): an edit as the paper's next version
        "workpaper.cells_set",
        "workpaper.cited",
        "workpaper.created",
        "workpaper.exported",  # A-04-T04: "Open in Excel", with the file's SHA-256
        "workpaper.signed_ready",
        "workpaper.signed_reviewed",
        "sending_domain.checked",  # R-01-T27
        "sending_domain.created",  # R-01-T27
        "sending_domain.failed",  # R-01-T27
        "sending_domain.revoked",  # R-01-T27
        "sending_domain.verified",  # R-01-T27
        "firm_mail_policy.client_mail_enabled",  # R-01-T27
        "firm_mail_policy.client_mail_disabled",  # R-01-T27
        "tax_return.status_changed",  # T-02-T07: a return's move (status events hold the detail)
        "tax_return.sync_recorded",  # T-02-T07: T-01's sync-chip write
        "envelope.polled",  # N-02-T13/T14 (S15)
        "signer.progress",  # N-02-T23
        "signer.esign_consent_accepted",  # N-02-T23
        "signer.signing_session_returned",  # N-02-T23
        "signer.signing_session_confirmed",  # N-02-T23
        "signed_copy.downloaded",  # N-02-T23
        "envelope.superseded",  # N-02-T25: C7 v1.1, the system's amount-change marker (S17)
        "envelope.retention_extended",  # N-02-T25: forward only
        "envelope.send_refused",  # N-02-T22: no consumed grant, nothing sent (S17)
        "evidence.downloaded",  # N-02-T13: the evidence zip (S15)
        "inbound_message.downloaded",  # N-01-T12 to T18 (S15)
        "inbox_attachment.downloaded",  # N-01-T12 to T18 (S15)
        "inbox_attachment.key_destroyed",  # N-01-T12 to T18 (S15)
        "inbox_attachment.triaged",  # N-01-T12 to T18 (S15)
        "inbox_attachment.viewed",  # N-01-T12 to T18 (S15)
        "inbox_attachment.waiting",  # N-01-T12 to T18 (S15)
        "inbox_sender_rule.created",  # N-01-T12 to T18 (S15)
        "inbox_thread.client_matched",  # N-01-T12 to T18 (S15)
        "inbox_thread.ignored",  # N-01-T12 to T18 (S15)
        "portal_intake.withdrawn",  # N-01-T12 to T18 (S15)
        "consent.expired",  # reviewed 2026-10-31 (S17-S19)
        "consent.exported",  # reviewed 2026-10-31 (S17-S19)
        "consent.reconsent_required",  # reviewed 2026-10-31 (S17-S19)
        "consent.recorded",  # reviewed 2026-10-31 (S17-S19)
        "consent.signed",  # reviewed 2026-10-31 (S17-S19)
        "engine.diagnostic_received",  # reviewed 2026-10-31 (S17-S19)
        "engine_export.downloaded",  # reviewed 2026-10-31 (S17-S19)
        "engine_export.generated",  # reviewed 2026-10-31 (S17-S19)
        "engine_export.marked_exported",  # reviewed 2026-10-31 (S17-S19)
        "engine_import.matched",  # reviewed 2026-10-31 (S17-S19)
        "engine_import.uploaded",  # reviewed 2026-10-31 (S17-S19)
        "engine_sync.acks_received",  # reviewed 2026-10-31 (S17-S19)
        "engine_sync.diagnostics",  # reviewed 2026-10-31 (S17-S19)
        "engine_sync.pdf_filed",  # reviewed 2026-10-31 (S17-S19)
        "envelope_policy.updated",  # S19 batch 4
        "evidence_version.duplicate_discarded",  # reviewed 2026-10-31 (S17-S19)
        "evidence_version.duplicate_kept",  # reviewed 2026-10-31 (S17-S19)
        "generated_document.locked",  # reviewed 2026-10-31 (S17-S19)
        "generated_document.marked_out_of_date",  # reviewed 2026-10-31 (S17-S19)
        "integration.settings_updated",  # reviewed 2026-10-31 (S17-S19)
        "letter.amended",  # S19 batch 4
        "letter.approval_requested",  # S19 batch 4
        "letter.approved",  # S19 batch 4
        "letter.drafted",  # reviewed 2026-10-31 (S17-S19)
        "letter.envelope_drafted",  # S19 batch 4
        "letter.envelope_ignored",  # S19 batch 4
        "mapping_set.confirmed",  # reviewed 2026-10-31 (S17-S19)
        "mapping_set.went_stale",  # reviewed 2026-10-31 (S17-S19)
        "methodology_import.cancelled",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_import.created",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_import.failed",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_import.needs_review",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_import.parsing",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_import.progressed",  # reviewed 2026-11-01 (K-01-T21)
        "methodology_source_file.downloaded",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_source_file.page_read",  # reviewed 2026-11-01 (K-01-T20)
        "methodology_source_file.pages_stored",  # reviewed 2026-11-01 (K-01-T21)
        "methodology_source_file.stored",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_source_file.words_read",  # reviewed 2026-11-01 (K-01-T20)
        "methodology_step.added",  # reviewed 2026-10-31 (S17-S19)
        "methodology_step.edited",  # reviewed 2026-10-31 (S17-S19)
        "methodology_step.flag_resolved",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_step.mandatory_changed",  # reviewed 2026-10-31 (S17-S19)
        "methodology_step.removed",  # reviewed 2026-10-31 (S17-S19)
        "methodology_version.discarded",  # reviewed 2026-10-31 (S17-S19)
        "methodology_version.draft_created",  # reviewed 2026-10-31 (S17-S19)
        "methodology_version.standards_mapped",  # reviewed 2026-10-31 (K-01-T18)
        "question.drafted",  # reviewed 2026-10-31 (S17-S19)
        "question.sent",  # reviewed 2026-10-31 (S17-S19)
        "questionnaire.answered",  # reviewed 2026-10-31 (S17-S19)
        "questionnaire.created",  # reviewed 2026-10-31 (S17-S19)
        "questionnaire_template.imported",  # reviewed 2026-10-31 (S17-S19)
        "questionnaire_template.published",  # reviewed 2026-10-31 (S17-S19)
        "disclosure_checklist_template.imported",  # reviewed 2026-11-06 (A-06-T28)
        "audit_misstatement.carried_from_py",  # reviewed 2026-11-06 (A-06-T28)
        "statement.management_approval_recorded",  # reviewed 2026-11-06 (A-06-T28)
        "statement.draft_requested",  # reviewed 2026-11-06 (A-06-T25)
        "statement.draft_failed",  # reviewed 2026-11-06 (A-06-T25)
        "statement.tie_out_requested",  # reviewed 2026-11-06 (A-06-T25)
        "disclosure_checklist_template.published",  # reviewed 2026-11-06 (A-06-T28)
        "disclosure_checklist.template_picked",  # reviewed 2026-11-07 (A-06-T25)
        "statement_note_template.imported",  # reviewed 2026-11-07 (A-06-T25)
        "statement_note_template.published",  # reviewed 2026-11-07 (A-06-T25)
        "deliverable.published",  # reviewed 2026-11-08 (R-02-T09)
        "deliverable.publish_repeated",  # reviewed 2026-11-08 (S31 end pass: idempotent retry)
        # reviewed 2026-11-09 (S32 end pass): the fallback reads each right.
        "agent_run.recorded_synthetic",
        "agent_tool.call_claimed",
        "agent_tool.call_completed",
        "agent_tool.call_released",
        "audit_report.choice_set",
        "governance_communication.acknowledgement_repeated",
        "governance_communication.approval_requested",
        "governance_communication.created",
        "governance_communication.envelope_drafted",  # TASK-6543: the fallback reads it right
        "governance_communication.sent",
        "governance_recipients.set",
        "deliverable.superseded",  # reviewed 2026-11-08 (R-02-T09)
        "deliverable.withdrawn",  # reviewed 2026-11-08 (R-02-T09)
        "assurance_checklist_template.imported",  # reviewed 2026-11-08 (A-07-T22)
        "assurance_checklist_template.published",  # reviewed 2026-11-08 (A-07-T22)
        "rep_letter.version_created",  # reviewed 2026-11-08 (A-07-T24)
        "rep_letter.approval_requested",  # reviewed 2026-11-08 (A-07-T24)
        "rep_letter.approved",  # reviewed 2026-11-08 (A-07-T24)
        "rep_letter.sent",  # reviewed 2026-11-08 (A-07-T24)
        "rep_letter.signed",  # reviewed 2026-11-08 (A-07-T24)
        "rep_letter.date_mismatch",  # reviewed 2026-11-08 (A-07-T24)
        "subsequent_event.procedure_added",  # reviewed 2026-11-08 (A-07-T23)
        "subsequent_event.procedure_performed",  # reviewed 2026-11-08 (A-07-T23)
        "subsequent_event.recorded",  # reviewed 2026-11-08 (A-07-T23)
        "legal_letter.recorded",  # reviewed 2026-11-08 (A-07-T23)
        "going_concern.decision_requested",  # reviewed 2026-11-08 (A-07-T23)
        "bring_down.completed",  # reviewed 2026-11-08 (A-07-T23)
        "completion.item_changed",  # reviewed 2026-11-08 (A-07-T22)
        "notice.respond_by_alerted",  # reviewed 2026-11-06 (N-04-T16)
        "notice.follow_up_alerted",  # reviewed 2026-11-06 (N-04-T16)
        "notice_response.payment_confirmation_decided",  # reviewed 2026-11-06 (N-04-T16)
        "upload.ocr_refused",  # reviewed 2026-11-06 (P-11-T25)
        "upload.text_ready",  # reviewed 2026-11-06 (P-11-T25)
        "questionnaire_template.drafted",  # reviewed 2026-11-06 (T-03-T05)
        "questionnaire_template.discarded",  # reviewed 2026-11-06 (T-03-T05)
        "questionnaire_template.owner_assigned",  # reviewed 2026-11-06 (T-03-T05)
        "recipient_details_change.accepted",  # S19 batch 4
        "recipient_details_change.rejected",  # S19 batch 4
        "report_template.deprecated",  # reviewed 2026-10-31 (S17-S19)
        "report_template.imported",  # reviewed 2026-10-31 (S17-S19)
        "report_template.published",  # reviewed 2026-10-31 (S17-S19)
        "signer.kba_failed",  # S19 batch 4
        "signer.verification_failed",  # S19 batch 4
        "signer.wet_signature_recorded",  # S19 batch 4
        "tax_authorization.added",  # reviewed 2026-10-31 (S17-S19)
        "tax_election.updated",  # reviewed 2026-10-31 (S17-S19)
        "tax_profile_file.staged",  # reviewed 2026-10-31 (S17-S19)
        "tax_return.approved",  # reviewed 2026-10-31 (S17-S19)
        "transcript.compared",  # reviewed 2026-10-31 (S17-S19)
        "transcript.uploaded",  # reviewed 2026-10-31 (S17-S19)
        "population.created",  # A-03-T07, T10: reviewed 2026-10-31
        "population.tie_recorded",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.created",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.drawn",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.override_requested",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.override_approved",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.approved",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.superseded",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.exported",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.draw_failed",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.draw_completed",  # A-03-T07, T10: reviewed 2026-10-31
        "sample_set.requests_generated",  # A-03-T13: the fan-out's counts and batch, 2026-11-01
        # S19 batch 5 (T-02-T20/T21): the K-1 set, its packages and the release gate.
        "schedule_k_set.imported",
        "schedule_k_package.shared_internal",
        "schedule_k_package.resend_requested",
        "schedule_k_package.released",
        "schedule_k_package.access_given",
        "schedule_k_package.deliverable_emailed",
        "schedule_k_package.handoff_replaced",
        "schedule_k_release.requested",
        "schedule_k_release.started",
        "schedule_k_release.undone",
        "schedule_k_release.contact_resolved",
        # T-02-T26: POR-13's recipient writes and a bounced "Deliverable ready".
        "recipient_details_change.submitted",
        "schedule_k_package.bounced",
        "schedule_k_package.e_furnishing_consent_recorded",
        "letter.envelope_withdrawn",  # N-02-T35: a person lets an unsigned envelope go
        # Reviewed 2026-11-01 (main CI triage): names that landed without an entry.
        "agent_run.completed",  # K-01-T21: an importer step's run ends
        # T-01-T35: the delivery packet's checklist and letter.
        "delivery_packet.approved",
        "delivery_packet.assembled",
        "delivery_packet.edited",
        "delivery_packet.letter_regenerated",
        # T-01-T36, T37: the 8879 amount binding, the transmission and its acknowledgements.
        "efile_binding.created",
        "efile_binding.superseded",
        "transmission.recorded",
        "efile_ack.imported",
        "efile_ack.recorded",
        "member.ero_designated",
        # T-01-T41: a filed return's delivery and its download.
        "return.delivered",
        "filed_return.downloaded",
        "generated_document.render_failed",  # P-11-T11: a render job that could not finish
        "methodology_version.exported",  # K-01-T16: a version's workbook export
        "schedule_k_disclosure.imported",  # POR-13 (TASK-2538): furnishing disclosures
        # A-04-T07: a work item's procedures written from its pinned version, a person's
        # tailoring, and the service-organization inventory's adds and edits.
        "procedure.instantiated",
        "procedure.tailored",
        "service_org.created",
        "service_org.edited",
        "section_draft.started",  # A-04-T11: a person started a section draft
        "section_draft.failed",  # A-04-T11: pack validation failed the run (AC6.1)
        # A-04-T12: materiality's versions, the partner's decision and reassessments applied.
        "materiality_version.proposed",
        "materiality_version.decided",
        "materiality_version.reassessed",
        "materiality_version.revised",
        # A-04-T13: the risk register's rows, field edits, proposals and responses.
        "risk.created",
        "risk.updated",
        "risk.significance_proposed",
        "risk.rebuttal_proposed",
        "risk.linked",
        "risk.unlinked",
        # A-05-T10: EBP-01's plan facts, providers, code checks and the plan number.
        "ebp_plan.created",
        "ebp_plan.edited",
        "ebp_provider.created",
        "ebp_check.recorded",
        "client_entity.plan_number_set",
        # S25 (A-04-T18, T19, T21; A-05-T16, T19; A-06-T09, T10, T11): reviewed onto the trail
        # with their own words in the record's activity (DEC-2077); no catalogue sentence yet.
        "risk_register.approved",
        "risk_register.returned",
        "fraud_session.recorded",
        "fraud_minutes.written",
        "fraud_minutes.approved",
        "fraud_inquiry.requested",
        "attention_flag.raised",
        "attention_flag.converted",
        "attention_flag.reminded",
        "ebp_plan_review.started",
        "ebp_provision.document_value_recorded",  # A-05-T16 (DEC-2489)
        "ebp_import.imported",
        "ebp_import.refused",
        "proposed_entry.proposed",
        "approval_batch.created",
        "proposed_entries.sent_to_client",
        "proposed_entries.send_undone",
        "audit_finding.recorded",
        "audit_finding.converted",
        "consultation.raised",
        "consultation.concluded",
        # S28 (TASK-3334): statements (A-06-T25), form extraction and OCR (P-11-T25, T26) and the
        # notice response (N-04-T16); the names read right through the fallback.
        "statement.drafted",
        "statement.tie_out_run",
        "disclosure_checklist.answered",
        "disclosure_checklist.adopted",
        "disclosure_checklist.reviewed",
        "extracted_fields.recorded",
        "upload.ocr_read",
        "notice_response.sent_for_signature",
        "notice_response.ready_to_send",
        "notice_response.sent",
        "notice.agency_reply_recorded",
        # reviewed 2026-11-06 (S27 gaps, TASK-3350 to TASK-3357)
        "audit_misstatement.effect_stated",
        "notice.analysis_started",
        "notice.analysis_failed",
        "audit_finding.raised_from_exception",
        "audit_misstatement.passed_on_sum",
        "audit_misstatement.raised_from_exception",
        "estimate_installment.confirmation_requested",
        "estimate_installment.due_soon_notified",
        "estimate_installment.recorded",
        "estimate_schedule.created",
        "estimate_schedule.inputs_updated",
        "filing_extension.ack_rejection_notified",
        "filing_extension.confirmation_requested",
        "filing_extension.due_date_recomputed",
        "filing_extension.figures_entered",
        "filing_extension.prepared",
        "filing_extension.submitted_for_approval",
        "soc_exception.impact_recorded",
        "soc_exception.routed",
        "sum.factor_recorded",
        "sum.snapshot_frozen",
        # reviewed 2026-11-12 (S38 end pass, TASK-7426): TIN seal and reveal stay in the audit
        # explorer only; residency and the engine sync chip show on their own screens.
        "partner.updated",
        "partner_tin.revealed",
        "residency_determination.confirmed",
        "residency_determination.opened",
        "tax_return.engine_reimport_needed",
        # DEC-4417: a run step holds on a card a person's own proposal raised (shown on the run).
        "agent_run.decision_held",
        # reviewed 2026-11-13 (S40 end pass): the search index's reindex is an operational record
        # (explorer only); workbook cell writes show in SHL-09's per-cell provenance and the
        # checkpoint list, not the engagement feed.
        "search_index.loadtest_seeded",  # S41 (TASK-7723): the local 1M load test's batches
        "search_index.reindex_completed",
        "search_index.reindex_requested",
        "workbook.cell_edited",
        "workbook.step_written",
        # reviewed 2026-11-13 (T-05-T37 rest, DEC-4629): the tax reviewer's mapping shows on
        # TXP-02's row and its Unmapped tally, not the engagement feed.
        "tax.mapping_recorded",
        # reviewed 2026-11-13 (S41, TASK-7701): an allocation structure's versions show on
        # TXP-06 and its approval is the L3 sign-off's own feed row.
        # reviewed 2026-11-13 (S41 CI fix, DEC-4735): a brief's build, the synthetic loaders'
        # records, the preparer memo's versions (TXP-01 shows them), the Workbench session's
        # own items (its thread shows them) and an imported report (its cells' provenance):
        # explorer only, not the engagement feed.
        "daily_briefing.built",
        "session.recorded_synthetic",
        "tax_entity.recorded_synthetic",
        "tax_memo.drafted",
        "tax_memo.regenerated",
        "workbench_session.context_added",
        "workbench_session.context_removed",
        "workbench_session.deleted",
        "workbench_session.renamed",
        "workbook_import.recorded",
        "allocation_structure.approved",
        "allocation_structure.drafted",
        "allocation_structure.proposed",
        # reviewed 2026-11-13 (S41, TASK-7703): sections open once per return (explorer only);
        # a section's sign-off and an acknowledged off tie-out show on TXP-07 and the sign-off
        # feed row.
        "tax_section.opened",
        "tax_section.signed_off",
        "tie_out.off_acknowledged",
        # reviewed 2026-11-13 (S42, TASK-7901): an approved workbook fix's cells (TXP-11 history
        # and the TXP-10 issue's activity).
        "workbook.fix_applied",
        # reviewed 2026-11-13 (S42, TASK-7902): the sealed note on resolving an issue no fix
        # closed (TXP-10 d's resolution line).
        "issue.resolution_noted",
        # reviewed 2026-11-13 (S42, TASK-7905): a workbook exported to xlsx (who, which version,
        # the file's hash; TXP-11's history).
        "workbook.exported",
        # reviewed 2026-11-13 (S42, TASK-7913): the Today brief's builds (dispatch, an
        # unavailable engagement recorded with its reason, the day's snapshot); no brief content.
        "daily_briefing.dispatched",
        "daily_briefing.unavailable",
        "daily_briefing.snapshot",
        # reviewed 2026-11-13 (S42 end pass, TASK-7922): a memo section's edit and the memo going
        # stale show on TXP-04's version list and the memo card; a session's title in WB-01.
        "tax_memo.section_edited",
        "tax_memo.went_stale",
        "workbench_session.titled",
    }
)
