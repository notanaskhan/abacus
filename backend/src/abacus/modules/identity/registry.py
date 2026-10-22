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
        "firm_policy_overrides",  # F-03-T24: stricter-only, never edited
        "client_access_grants",  # F-03-T26 (ADR-146)
        "client_access_events",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset({"firm_policy_overrides", "client_access_events"})
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "engagement_members": frozenset({"tenant_id", "engagement_id", "user_id", "role"}),
    "ethical_walls": frozenset({"id", "tenant_id", "user_id", "client_id", "created_by"}),
    # Break-glass (SPEC-012): requested by staff; lifecycle columns updated as it is approved.
    "support_sessions": frozenset(
        {"id", "tenant_id", "staff_id", "staff_subject", "reason", "scope", "duration_minutes"}
        | {"emergency"}
    ),
    # Client invitations (SPEC-015): never the token (only its hash, elsewhere).
    "client_invitations": frozenset(
        {"id", "tenant_id", "engagement_id", "email", "role", "invited_by", "expires_at"}
    ),
    "staff_invitations": frozenset(  # SPEC-024 (TASK-041)
        {"id", "tenant_id", "email", "firm_role", "invited_by", "expires_at"}
    ),
    "firm_setting_values": frozenset({"tenant_id", "key", "value", "set_by"}),  # F-03-T24
    "firm_policy_overrides": frozenset(  # F-03-T24
        {"tenant_id", "action", "role", "decision", "reason", "set_by"}
    ),
    "client_access_grants": frozenset(  # F-03-T26
        {"tenant_id", "user_id", "contact_id", "role", "scope_kind", "scope_id"}
        | {"document_classes", "granted_by", "expires_at", "status"}
    ),
    "client_access_events": frozenset({"tenant_id", "grant_id", "event", "by_user_id"}),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # SPEC-024 (TASK-042): the firm's autonomy level and its onboarding acknowledgements.
    "firms": frozenset(
        {"autonomy_level", "autonomy_set_at", "budget_reviewed_at", "walls_none_needed_at"}
        | {"sso_skipped_at", "onboarding_dismissed_at"}
        | {"require_letter"}  # SPEC-025 (TASK-044)
        | {"drafted_guidance_to_clients"}  # SPEC-035 (TASK-073)
        | {"ai_client_data_at", "ai_client_data_by", "ai_client_data_material"}  # SPEC-036
        | {"agents_paused_at", "agents_paused_by"}  # SPEC-027 (TASK-050): the firm switch
        | {"time_zone"}  # SPEC-027 (TASK-051): the agent's daily tick
    ),
    "ethical_walls": frozenset({"status", "removed_by", "removed_at"}),
    "support_sessions": frozenset(  # SPEC-012: lifecycle only
        {"status", "approved_by_kind", "approved_by", "starts_at", "expires_at", "ended_at"}
        | {"acknowledged_at"}
    ),
    "client_invitations": frozenset({"status", "accepted_by", "accepted_at", "expires_at"}),
    "staff_invitations": frozenset({"status", "accepted_by", "accepted_at", "expires_at"}),
    "firm_setting_values": frozenset({"value", "version", "set_by", "set_at"}),  # F-03-T24
    "client_access_grants": frozenset({"status"}),  # F-03-T26: each change is an event row
}
