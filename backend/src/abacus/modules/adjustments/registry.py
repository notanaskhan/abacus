"""The adjustments module's registry (P-39; F-03-T07).

The tables it owns (ADR-103) and what the app role may do with them. A-06-T03 (0643, DEC-1962):
proposed entries and their lines, insert-only decisions and approval batches.
"""

from __future__ import annotations

TABLES: frozenset[str] = frozenset(
    {"proposed_entries", "proposed_entry_lines", "proposed_entry_decisions", "approval_batches"}
)
INSERT_ONLY: frozenset[str] = frozenset({"proposed_entry_decisions", "approval_batches"})
INSERT_COLUMNS: dict[str, frozenset[str]] = {
    "proposed_entries": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "kind",
            "number",
            "ref",
            "description",
            "misstatement_id",
            "source_ref",
            "amount",
            "account_class",
            "threshold_policy_version_id",
            "threshold_result",
            "is_attest_client",
            "status",
            "client_wording_template_version_id",
            "created_by_kind",
            "created_by_id",
            "on_behalf_of_user_id",
        }
    ),
    "proposed_entry_lines": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "entry_id",
            "line_no",
            "account_code",
            "account_name",
            "fs_line_key",
            "debit",
            "credit",
            "account_scope",  # T-05-T25 (0841): book or tax_only
        }
    ),
    "proposed_entry_decisions": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "entry_id",
            "decision",
            "actor_principal",
            "client_grant_id",
            "channel",
            "reason_code",
            "note_sealed",
            "evidence_version_id",
            "approval_batch_id",
            "approval_grant_id",
            "seen_version",
        }
    ),
    "approval_batches": frozenset(
        {
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "policy_version_id",
            "entry_ids",
            "approver_user_id",
            "label",
        }
    ),
}
UPDATE_COLUMNS: dict[str, frozenset[str]] = {
    "proposed_entries": frozenset(
        {
            "status",
            "description",
            "amount",
            "account_class",
            "version",
        }
    ),
    "proposed_entry_lines": frozenset(
        {
            "account_code",
            "account_name",
            "fs_line_key",
            "debit",
            "credit",
        }
    ),
}

# S46: A-09-T10 (0896) elimination columns.
INSERT_COLUMNS["proposed_entries"] = INSERT_COLUMNS.get(
    "proposed_entries", frozenset()
) | frozenset(
    {
        "account_class",
        "amount",
        "client_wording_template_version_id",
        "consolidation_id",
        "created_by_id",
        "created_by_kind",
        "description",
        "display_code",
        "engagement_id",
        "is_attest_client",
        "kind",
        "misstatement_id",
        "number",
        "on_behalf_of_user_id",
        "posting_target",
        "ref",
        "source_ref",
        "status",
        "tenant_id",
        "threshold_policy_version_id",
        "threshold_result",
        "work_item_id",
    }
)
UPDATE_COLUMNS["proposed_entries"] = UPDATE_COLUMNS.get(
    "proposed_entries", frozenset()
) | frozenset({"account_class", "amount", "description", "status", "version"})
INSERT_COLUMNS["proposed_entry_lines"] = INSERT_COLUMNS.get(
    "proposed_entry_lines", frozenset()
) | frozenset(
    {
        "account_code",
        "account_name",
        "account_scope",
        "client_entity_id",
        "consolidation_level",
        "credit",
        "debit",
        "engagement_id",
        "entry_id",
        "fs_line_key",
        "line_no",
        "tenant_id",
        "work_item_id",
    }
)
UPDATE_COLUMNS["proposed_entry_lines"] = UPDATE_COLUMNS.get(
    "proposed_entry_lines", frozenset()
) | frozenset(
    {
        "account_code",
        "account_name",
        "client_entity_id",
        "consolidation_level",
        "credit",
        "debit",
        "fs_line_key",
    }
)
