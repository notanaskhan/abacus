"""The practice module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them.
"""

from __future__ import annotations

# I-01-T12 (migration 0320): HOME-01's client activity projection. Inserted once per event and
# pruned after 90 days (the app role may delete), never updated.
TABLES: frozenset[str] = frozenset({"home_activity_items"})
INSERT_ONLY: frozenset[str] = frozenset()
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "home_activity_items": frozenset(
        {"tenant_id", "source_event_id", "event_type", "occurred_at", "client_id"}
        | {"engagement_id", "work_item_id", "office_id", "actor_kind", "actor_ref"}
        | {"subject_ref", "facts"}
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {}

# T-08-T07 (0962, DEC-5606).
T08T07_TABLES: frozenset[str] = frozenset(
    {
        "filing_deadline_alerts",
        "filing_deadlines",
    }
)
TABLES = TABLES | T08T07_TABLES
INSERT_ONLY = INSERT_ONLY | frozenset(
    {
        "filing_deadline_alerts",
    }
)
INSERT_COLUMNS["filing_deadlines"] = frozenset(
    {
        "client_id",
        "done_at",
        "due_on",
        "extended_due_on",
        "extension_filed_on",
        "extension_form",
        "filing_label",
        "inputs_hash",
        "internal_target_on",
        "office_id",
        "original_due_on",
        "owner_user_ids",
        "postponed_from",
        "postponement_notice_id",
        "reference_set_version_ids",
        "rule_key",
        "service_line",
        "signer_user_id",
        "source_kind",
        "source_ref",
        "stage_code",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["filing_deadlines"] = frozenset(
    {
        "client_id",
        "computed_at",
        "done_at",
        "due_on",
        "extended_due_on",
        "extension_filed_on",
        "extension_form",
        "inputs_hash",
        "internal_target_on",
        "office_id",
        "original_due_on",
        "owner_user_ids",
        "postponed_from",
        "postponement_notice_id",
        "reference_set_version_ids",
        "rule_key",
        "service_line",
        "signer_user_id",
        "stage_code",
        "work_item_id",
    }
)
INSERT_COLUMNS["filing_deadline_alerts"] = frozenset(
    {
        "due_on",
        "filing_deadline_id",
        "tenant_id",
        "threshold",
    }
)
