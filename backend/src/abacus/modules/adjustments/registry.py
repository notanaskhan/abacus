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
