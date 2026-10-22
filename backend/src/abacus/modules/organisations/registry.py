"""The organisations module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    {
        "clients",
        "client_entities",
        # F-03-T23 (DEC-30): offices are a filter, never an access boundary (Q-21).
        "offices",
        "teams",
        "team_rosters",
        "contacts",  # F-03-T25 (0082)
    }
)
# Insert and read, never update or delete, for the app role (ADR-004).
INSERT_ONLY: frozenset[str] = frozenset()
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "clients": frozenset({"id", "tenant_id", "name"}),
    "client_entities": frozenset({"id", "tenant_id", "client_id", "name"}),
    "offices": frozenset({"tenant_id", "name", "time_zone"}),
    "teams": frozenset({"tenant_id", "office_id", "name"}),
    "team_rosters": frozenset({"tenant_id", "team_id", "user_id"}),
    "contacts": frozenset(  # F-03-T25 (0082)
        {"id", "tenant_id", "client_id", "display_name", "email", "phone", "title"}
        | {"organisation_name", "contact_kind"}
    ),
}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    # F-03-T25 (0082): the client record (DEC-62). `is_attest_client` is the database's to
    # derive (DEC-128), never the app's.
    "clients": frozenset(
        {"kind", "status", "primary_office_id", "relationship_partner_id", "risk_tier"}
        | {"portal_status", "practice_mgmt_ref"}
    ),
    "client_entities": frozenset(
        {"entity_type", "fye_month_day", "state_of_formation", "plan_number", "date_of_death"}
        | {"grantor_status"}
    ),
    "contacts": frozenset(
        {"display_name", "phone", "title", "organisation_name", "user_id", "portal_state"}
    ),
}
