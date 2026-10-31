"""The identity module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "firms",
        "users",
        "memberships",
        "engagement_members",
        "engagement_member_events",  # P-07-T30 (0155): the membership history, insert-only
        "ethical_walls",
        "support_sessions",  # SPEC-012
        "client_invitations",
        "invitation_tokens",
        "invitation_failures",
        "signup_codes",
        "signup_attempts",
        "staff_invitations",
        "staff_invitation_tokens",
        "firm_setting_values",  # F-03-T24
        "firm_settings",  # G-01-T04 (0114): the typed store
        "firm_settings_sections",  # G-01-T04: one version per section
        "firm_policy_overrides",  # F-03-T24: stricter-only, never edited
        "client_access_grants",  # F-03-T26 (ADR-146)
        "client_access_events",
        "firm_demo_clocks",  # F-04-T06: synthetic firms only
        "auth_login_states",  # P-01-T09 (ADR-165): global, definers only
        "auth_sessions",
        "auth_session_cookies",
        "sign_in_challenges",  # P-08-T10 (ADR-168): global, definers only
        "sign_in_locks",
        "mfa_factors",  # P-08-T17 (0133): global, definers only
        "mfa_backup_codes",
        "trusted_devices",
        "portal_security_policies",  # P-08-T17: the firm's stricter-only floor extension
        "approval_grants",  # P-04-T10 (ADR-161): settled once, by consume or void
        "service_line_policies",  # G-01-T12 (0167): who reads a service line's content
        # G-01-T13 (0168): the annual independence statement and confirmations (DEC-91), and the
        # access-end job's notices.
        "independence_statements",
        "independence_annual_confirmations",
        "access_end_notices",
        # G-02-T14 (0220): the firm's security policies and per-firm session sign-outs.
        "security_policies",
        "auth_session_tenant_revocations",
        # P-07-T47 (0360): the invitation-expiry pass's notices (DEC-1000).
        "invitation_expiry_notices",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {"firm_policy_overrides", "client_access_events"}
    | {"engagement_member_events"}  # P-07-T30 (0155)
    # G-01-T13 (0168)
    | {"independence_statements", "independence_annual_confirmations", "access_end_notices"}
    | {"auth_session_tenant_revocations"}  # G-02-T14 (0220)
    | {"invitation_expiry_notices"}  # P-07-T47 (0360)
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    # G-02-T14 (0220): a live person's policy row (the trigger), and their per-firm sign-out.
    "security_policies": frozenset(
        {"tenant_id", "require_sso", "sso_enforced_at", "sso_enforced_by"}
        | {"idp_mfa_attested_at", "idp_mfa_attested_by", "session_absolute_minutes"}
        | {"session_idle_minutes", "sso_exempt_user_id", "allow_support_requests"}
        | {"support_updated_at", "support_updated_by", "support_version", "updated_by"}
    ),
    "auth_session_tenant_revocations": frozenset(
        {"tenant_id", "session_id", "user_id", "revoked_by"}
    ),
    "portal_security_policies": frozenset({"tenant_id", "portal_session_minutes", "updated_by"}),
    "engagement_members": frozenset({"tenant_id", "engagement_id", "user_id", "role"}),
    # P-07-T30 (0155): written by the `engagement_member_history` trigger as the caller.
    "engagement_member_events": frozenset(
        {"tenant_id", "engagement_id", "user_id", "role", "event"}
    ),
    "ethical_walls": frozenset(
        {"id", "tenant_id", "user_id", "client_id", "created_by"}
        | {"reason_code", "reason_text", "approver_user_id"}  # G-01-T09 (0151): walls v2
    ),
    # Break-glass (SPEC-012): requested by staff; lifecycle columns updated as it is approved.
    "support_sessions": frozenset(
        {"id", "tenant_id", "staff_id", "staff_subject", "reason", "scope", "duration_minutes"}
        | {"emergency"}
    ),
    # Client invitations (SPEC-015): never the token (only its hash, elsewhere).
    "client_invitations": frozenset(
        {"id", "tenant_id", "engagement_id", "email", "role", "invited_by", "expires_at"}
        # P-08-T18 (0140): invitations v2.
        | {"kind", "contact_id", "grant_template", "terms_version", "terms_url"}
        | {"grant_ids"}  # P-07-T25 (0146): a contact invitation's pending grants
    ),
    "staff_invitations": frozenset(  # SPEC-024 (TASK-041)
        {"id", "tenant_id", "email", "firm_role", "invited_by", "expires_at"}
        # G-01-T05 (0142): what the membership takes on acceptance.
        | {"role_template", "level", "office_id", "team_ids", "service_lines", "access_ends_on"}
        | {"offshore", "display_name", "job_title"}
    ),
    "firm_setting_values": frozenset({"tenant_id", "key", "value", "set_by"}),  # F-03-T24
    "firm_settings": frozenset({"tenant_id", "section", "key", "value", "updated_by"}),  # G-01-T04
    "firm_settings_sections": frozenset({"tenant_id", "section"}),  # G-01-T04
    "firm_policy_overrides": frozenset(  # F-03-T24
        {"tenant_id", "action", "role", "decision", "reason", "set_by"}
    ),
    "client_access_grants": frozenset(  # F-03-T26
        {"tenant_id", "user_id", "contact_id", "role", "scope_kind", "scope_id"}
        | {"document_classes", "granted_by", "expires_at", "status"}
    ),
    "client_access_events": frozenset({"tenant_id", "grant_id", "event", "by_user_id"}),
    "firm_demo_clocks": frozenset({"tenant_id", "mode", "anchor_at", "set_by"}),  # F-04-T06
    "approval_grants": frozenset(  # P-04-T10
        {"tenant_id", "subject_type", "subject_id", "action", "approver_user_id"}
        | {"engagement_id", "work_item_id", "payload_sha256", "not_before", "expires_at"}
    ),
    "service_line_policies": frozenset(  # G-01-T12 (0167)
        {"tenant_id", "service_line", "enabled", "lead_user_id", "content_visible_to"}
        | {"cross_line_access", "updated_by"}
    ),
    # G-01-T13 (0168): versions, decisions and notices; times and actor kinds are server-set.
    "independence_statements": frozenset({"tenant_id", "version", "body", "created_by"}),
    "independence_annual_confirmations": frozenset(
        {"tenant_id", "user_id", "year", "decision", "note", "statement_version"}
    ),
    "access_end_notices": frozenset({"tenant_id", "access_ends_on", "members"}),
    # P-07-T47 (0360): one notice per invitation and expiry.
    "invitation_expiry_notices": frozenset({"tenant_id", "invitation_id", "expires_at"}),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # G-02-T14 (0220): edited in place against `version` / `support_version`; never deleted.
    "security_policies": frozenset(
        {"require_sso", "sso_enforced_at", "sso_enforced_by", "idp_mfa_attested_at"}
        | {"idp_mfa_attested_by", "session_absolute_minutes", "session_idle_minutes"}
        | {"sso_exempt_user_id", "sso_exempt_tested_at", "allow_support_requests"}
        | {"support_updated_at", "support_updated_by", "version", "support_version"}
        | {"updated_by", "updated_at"}
    ),
    "portal_security_policies": frozenset(
        {"portal_session_minutes", "version", "updated_by", "updated_at"}
    ),
    # SPEC-024 (TASK-042): the firm's autonomy level and its onboarding acknowledgements.
    "firms": frozenset(
        {"autonomy_level", "autonomy_set_at", "budget_reviewed_at", "walls_none_needed_at"}
        | {"sso_skipped_at", "onboarding_dismissed_at"}
        | {"require_letter"}  # SPEC-025 (TASK-044)
        | {"drafted_guidance_to_clients"}  # SPEC-035 (TASK-073)
        | {"ai_client_data_at", "ai_client_data_by", "ai_client_data_material"}  # SPEC-036
        | {"agents_paused_at", "agents_paused_by"}  # SPEC-027 (TASK-050): the firm switch
        | {"time_zone"}  # SPEC-027 (TASK-051): the agent's daily tick
        | {"kms_key_arn", "kms_key_status", "kms_replica_verified_at"}  # Q-01-T19: key workflow
    ),
    "ethical_walls": frozenset(
        {"status", "removed_by", "removed_at"}
        | {"approved_by", "approved_at", "removed_reason"}  # G-01-T09 (0151): set once each
    ),
    # P-07-T30 (0155): ENG-05's hours and POR-02's team card; roles stay behind the definers.
    "engagement_members": frozenset({"budget_hours", "shown_on_portal"}),
    "memberships": frozenset(
        {"default_office_filter_id"}  # P-01-T04: the person's own, via /v1/me
        # G-01-T05 (0142): a person's template and attributes; firm roles stay behind definers.
        | {"role_template", "level", "job_title", "office_id", "service_lines", "access_ends_on"}
        | {"offshore", "version"}
        | {"ero_designated"}  # T-01-T37 (0568): the firm admin's ERO designation
    ),
    "support_sessions": frozenset(  # SPEC-012: lifecycle only
        {"status", "approved_by_kind", "approved_by", "starts_at", "expires_at", "ended_at"}
        | {"acknowledged_at"}
    ),
    "client_invitations": frozenset(
        {"status", "accepted_by", "accepted_at", "expires_at", "terms_accepted_at"}  # 0140
        | {"used_at", "grant_ids"}  # 0146 (P-07-T25)
        | {"renewal_count"}  # 0156 (P-08-T21): a recipient's renewal, at most twice
    ),
    "staff_invitations": frozenset({"status", "accepted_by", "accepted_at", "expires_at"}),
    "firm_setting_values": frozenset({"value", "version", "set_by", "set_at"}),  # F-03-T24
    "firm_settings": frozenset({"value", "updated_by", "updated_at"}),  # G-01-T04
    "firm_settings_sections": frozenset({"version", "updated_at"}),  # G-01-T04
    # F-03-T26: each change is an event row. P-07-T25 (0146): `user_id` once, as a pending grant
    # activates (trigger `client_access_grants_bind`).
    "client_access_grants": frozenset({"status", "user_id"}),
    "firm_demo_clocks": frozenset(  # F-04-T07: set or reset by the demo-clock service
        {"mode", "anchor_at", "anchored_real_at", "set_by", "set_at"}
    ),
    "approval_grants": frozenset({"used_at", "consumer_ref", "voided_at"}),  # P-04-T10
    "service_line_policies": frozenset(  # G-01-T12 (0167): against `version`; never deleted
        {"enabled", "lead_user_id", "content_visible_to", "cross_line_access", "version"}
        | {"updated_by", "updated_at"}
    ),
}
