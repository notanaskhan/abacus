"""The platform module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. The quality gate collects
every module's registry (schema_check), so adding a table edits only this file.
"""

from __future__ import annotations

# The tables this module owns; no other module reads or writes them (ADR-008).
TABLES: frozenset[str] = frozenset(
    # Q-01-T19 (ADR-157): global, no app privileges; through definer functions only.
    {"platform_controls", "platform_control_changes", "firm_provisioning_requests"}
    # F-03-T28 (ADR-148): plans (global) and the firms' module entitlements (read-only to the app).
    | {"plans", "tenant_entitlements"}
    | {"plan_modules"}  # Q-01-T45 (0107)
    | {"security_incidents"}  # Q-02-T33 (0143): the firm's incident register
    | {"incident_propagations"}  # Q-02-T33 (0143): global staff record; definers only
)
# Insert and read, never update or delete, for the app role (ADR-004).
# Q-02-T33: incidents are insert-only until G-02-T18 grants the status change with its decisions.
INSERT_ONLY: frozenset[str] = frozenset(
    {"platform_control_changes", "security_incidents", "incident_propagations"}
)
# Columns the app may supply on insert; everything else is server-set.
INSERT_COLUMNS: dict[str, frozenset[str]] = {}
# Columns the app may update; tables not listed keep what their migration grants.
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}
