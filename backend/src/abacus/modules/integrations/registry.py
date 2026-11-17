"""The integrations module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {
        # 0194 (A-02-T12): global catalogue content; the app reads it through
        # `integration_catalog_rows()` and holds no privilege on the table.
        "integration_catalog",
        "firm_integrations",
        "integration_secrets",
        "integration_mappings",  # 0466 (T-01-T20)
        # W-01-T04 (0890): C20 v2 Connect.
        "integration_catalog_imports",  # platform; the operator writes, definers read
        "user_integrations",
        "integration_oauth_states",
        "integration_events",
        "integration_interest",
    }
)
INSERT_ONLY: frozenset[str] = frozenset({"integration_events"})  # W-01-T04: append-only
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset(
        {"tenant_id", "catalog_key", "status", "mode", "created_by"}
        # W-01-T04 (0890): the drawer's facts.
        | {"status_reason_code", "status_changed_at", "token_renews_at", "granted_scopes"}
        | {"consent_version", "connected_by", "connected_at"}
    ),
    # Sealed once, never updated; deleting the row removes the only sealed copy.
    "integration_secrets": frozenset(
        {"tenant_id", "firm_integration_id", "sealed", "key_id"}
        | {"user_integration_id"}  # W-01-T04 (0890): a personal install's secret
    ),
    "user_integrations": frozenset(
        {"tenant_id", "user_id", "catalog_key", "status", "status_reason_code"}
        | {"status_changed_at", "connected_at", "token_renews_at", "granted_scopes"}
        | {"consent_version"}
    ),
    "integration_oauth_states": frozenset(
        {"state_sha256", "tenant_id", "user_id", "catalog_key", "scope_kind", "purpose"}
        | {"pkce_verifier_sealed", "expires_at"}
    ),
    "integration_events": frozenset(
        {"tenant_id", "install_kind", "install_id", "catalog_key", "kind", "at"}
        | {"actor_user_id", "subject_type", "subject_id", "run_id", "code", "http_status"}
        | {"latency_ms"}
    ),
    "integration_interest": frozenset({"tenant_id", "user_id", "catalog_key"}),
    # T-01-T20 (0466): ADM-08's settings and mappings.
    "integration_mappings": frozenset(
        {"tenant_id", "firm_integration_id", "kind", "source_key", "target_value", "direction"}
        | {"updated_by"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "firm_integrations": frozenset(
        {"status", "version"}
        | {"status_reason_code", "status_changed_at", "token_renews_at", "last_sync_at"}
        | {"granted_scopes", "consent_version", "connected_by", "connected_at"}
    ),
    "user_integrations": frozenset(
        {"status", "status_reason_code", "status_changed_at", "connected_at", "token_renews_at"}
        | {"last_sync_at", "granted_scopes", "consent_version", "version"}
    ),
    "integration_oauth_states": frozenset({"spent_at"}),
    "integration_interest": frozenset({"notified_at"}),
    "integration_mappings": frozenset(
        {"target_value", "direction", "version", "updated_by", "updated_at"}
    ),
}

# C-02-T05 (0951, DEC-5504): W1 write operations and their evidence, the client's write grants,
# the firm switch's history and the engagement's posting switch.
C02T05_TABLES: frozenset[str] = frozenset(
    {
        "ledger_write_operations",
        "ledger_write_evidence",
        "connection_write_grants",
        "firm_write_capabilities",
        "connection_engagement_settings",
    }
)
TABLES = TABLES | C02T05_TABLES
INSERT_ONLY = INSERT_ONLY | frozenset(
    {"ledger_write_evidence", "connection_write_grants", "firm_write_capabilities"}
)
INSERT_COLUMNS["ledger_write_operations"] = frozenset(
    {
        "tenant_id",
        "capability_id",
        "client_entity_id",
        "connection_id",
        "subject_type",
        "subject_id",
        "operation",
        "idempotency_key",
        "approval_grant_id",
        "actor_user_id",
    }
)
INSERT_COLUMNS["ledger_write_evidence"] = frozenset(
    {"tenant_id", "write_operation_id", "kind", "object_key", "sha256", "bytes"}
)
INSERT_COLUMNS["connection_write_grants"] = frozenset(
    {
        "tenant_id",
        "connection_id",
        "client_entity_id",
        "capability_id",
        "consent_copy_version",
        "granted_by_client_user_id",
        "mfa_at",
        "event",
        "actor_id",
    }
)
INSERT_COLUMNS["firm_write_capabilities"] = frozenset(
    {"tenant_id", "capability_id", "enabled", "changed_by", "mfa_at", "reason"}
)
INSERT_COLUMNS["connection_engagement_settings"] = frozenset(
    {
        "tenant_id",
        "engagement_id",
        "connection_id",
        "posting_enabled",
        "posting_enabled_by",
        "posting_enabled_at",
    }
)
UPDATE_COLUMNS["ledger_write_operations"] = frozenset(
    {"status", "provider_request_id", "external_ref", "attempt", "started_at", "finished_at"}
)
UPDATE_COLUMNS["connection_engagement_settings"] = frozenset(
    {"posting_enabled", "posting_enabled_by", "posting_enabled_at", "version"}
)
