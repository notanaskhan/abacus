"""The portal module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# P-08-T05 (0111): branding, hosts and preferences. `portal_domains` is global and reached only
# through definer functions; branding is read before sign-in only through the host lookups.
TABLES: frozenset[str] = frozenset({"portal_branding", "portal_domains", "portal_preferences"})
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "portal_branding": frozenset(
        {"tenant_id", "display_name", "portal_name", "logo_png", "logo_sha256", "address_line"}
        | {"help_url", "privacy_url", "terms_url", "terms_version", "support_contact_user_id"}
        | {"support_contact_name", "secured_footer", "maintenance_banner", "updated_by"}
    ),
    "portal_preferences": frozenset(
        {"tenant_id", "user_id", "scope_kind", "scope_id", "welcome_dismissed_at"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "portal_branding": frozenset(
        {"display_name", "portal_name", "logo_png", "logo_sha256", "address_line", "help_url"}
        | {"privacy_url", "terms_url", "terms_version", "support_contact_user_id"}
        | {"support_contact_name", "secured_footer", "maintenance_banner", "version"}
        | {"updated_by", "updated_at"}
    ),
    "portal_preferences": frozenset({"welcome_dismissed_at", "version", "updated_at"}),
}
