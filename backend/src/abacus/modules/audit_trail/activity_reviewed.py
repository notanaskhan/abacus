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
        "approval_grant.consumed",
        "approval_grant.voided",
        "archive.locked",
        "assurance.archive_recorded",  # A-01-T23: export id, manifest digest, never the ref
        "assurance.phase_derived",
        "assurance.phase_recorded",
        "assurance.profile_updated",
        "assurance.release_recorded",  # A-01-T23: the recorded date and kind, as numbers
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
        "decision.refused_non_human",  # K-01-T06: an agent or the platform asked to approve
        "envelope.draft_saved",  # N-02-T20: SIG-02's edit of a draft (version, signer count)
        "envelope.drafted",  # N-02-T20: a draft from a registered source (number, counts)
        "envelope.imported",  # N-02-T08: record-mode import (SIG-01 r)
        "envelope.provider_hint",  # N-02-T19: a verified Connect hint (duplicate flag only)
        "envelope.provider_unavailable",  # N-02-T18: kill switch, W7 or install off; not sent
        "envelope.send_requested",  # N-02-T20: a person's Send, waiting its grant (+10 s)
        "envelope.send_undone",  # N-02-T20: Undo inside the window; no provider call
        "envelope_import_file.staged",  # N-02-T08: a scanned file for an import
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
        "report.released",
        "representation.added",
        "representation.removed",
        "request_item.client_assigned",
        "request_item.client_visibility_changed",
        "request_item.created",
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
        "sign_off.recorded",
        "sign_off.went_stale",
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
        "workpaper.cells_set",
        "workpaper.cited",
        "workpaper.created",
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
        "envelope.evidence_recorded",  # N-02-T13/T14 (S15)
        "envelope.expired",  # N-02-T13/T14 (S15)
        "envelope.polled",  # N-02-T13/T14 (S15)
        "envelope.reminder_skipped",  # N-02-T13/T14 (S15)
        "envelope.voided",  # N-02-T13/T14 (S15)
        "envelope.viewed",  # N-02-T23: POR-06 (S17)
        "envelope.declined",  # N-02-T23
        "envelope.decline_withdrawn",  # N-02-T23
        "signer.progress",  # N-02-T23
        "signer.esign_consent_accepted",  # N-02-T23
        "signer.signing_session_issued",  # N-02-T23
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
        "methodology_source_file.downloaded",  # reviewed 2026-10-31 (K-01-T18)
        "methodology_source_file.stored",  # reviewed 2026-10-31 (K-01-T18)
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
    }
)
