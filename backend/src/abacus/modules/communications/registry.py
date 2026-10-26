"""The communications module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "messages",
        # P-01-T05 (C16): platform-wide, reached only through definer functions (0092).
        "email_templates",
        "email_template_versions",
        # Q-01-T46 (0104): what SES said about each send, and addresses not to mail again.
        "message_deliveries",
        "email_suppressions",
        # P-08-T21 (0156): portal emails' secure links; only the token's hash is kept.
        "secure_links",
        # R-01-T19 (0196): a firm's unpublished template edit, sealed with the firm's key.
        "email_template_drafts",
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset(
    {
        "messages",
        "message_deliveries",
    }
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "messages": frozenset(
        {"id", "tenant_id", "engagement_id", "channel", "recipient_ref", "body", "status"}
        | {"violations", "created_by"}
        | {"template_version_id", "kind"}  # R-01-T19 (0196)
    ),
    "message_deliveries": frozenset(
        {"tenant_id", "message_id", "provider_event_id", "event", "bounce_kind", "occurred_at"}
    ),
    "email_suppressions": frozenset({"tenant_id", "address_hash", "reason"}),
    "secure_links": frozenset(
        {"id", "tenant_id", "contact_id", "purpose", "target_kind", "target_id"}
        | {"recipient_email", "host", "token_sha256", "issued_by", "expires_at"}
        | {"renewed_from_id", "chain_started_at", "chain_length"}  # a renewal, in the firm
    ),
    # R-01-T19 (0196): one draft per firm and template; deleted on discard and publish.
    "email_template_drafts": frozenset(
        {"tenant_id", "template_id", "base_version_id", "sealed", "cta_target"}
        | {"draft_version", "updated_by"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "email_suppressions": frozenset({"lifted_at", "lifted_by"}),  # Q-01-T46: lifting only
    # P-08-T21: a renewed link's token at delivery, and revocation.
    "secure_links": frozenset({"token_sha256", "revoked_at"}),
    # R-01-T19 (0196): a draft save replaces the content and who saved it.
    "email_template_drafts": frozenset(
        {"base_version_id", "sealed", "cta_target", "draft_version", "updated_by", "updated_at"}
    ),
}
