"""The reviewed exemption registry of `archived_guard()` (A-07-T13; ADR P-43; A-07 F8). PROTECTED.

Every table with a `work_item_id` or `engagement_id` column carries the guard: once a work item is
locked (or its engagement archived), a write raises `archived`. A table stays out only if it is
listed here with a reason: it governs retention or delivery, or it records someone reading the
file, not the file's documentation. Adding a row here is a red diff.

`ALLOWED_KINDS` names the tables a write may reach after lock, and under which `archived_write`
kind. Only `UnitOfWork.allow_archived_write` sets that setting (ARCHIVE-001).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Literal, get_args

ArchivedWriteKind = Literal[
    "archive_addition", "post_issuance", "retention_extend", "destruction_tombstone"
]
ARCHIVED_WRITE_KINDS: Final = frozenset(get_args(ArchivedWriteKind))
ARCHIVED_SQLSTATE: Final = "AB409"

EXEMPT: Final[Mapping[str, str]] = {
    "access_events": "logs who read the file, which must go on after lock",
    "tin_reveals": "logs a reveal, a read",
    "audit_events": "the append-only trail outlives every lock (I-IMMUTABLE)",
    "audit_event_labels": "a trail label, not documentation",
    "notifications": "delivery",
    "reminders": "delivery",
    "home_activity_items": "a rebuildable projection for Home",
    "human_gates": "C13's projection; archive.locked itself clears rows here",
    "messages": "delivery; a bounce or receipt arrives after lock",
    "approval_grants": "a send's grant expires or voids after lock",
    "agent_runs": "a run in flight at lock must still end, failed",
    "agent_run_records": "a run's record; the run ending after lock",
    "agent_activity": "a run's activity, not documentation",
    "binder_activity": "a rebuildable projection for the binder",
    "attention_flags": "an operational flag on the row, not documentation",
    "attention_flag_events": "an operational flag's history",
    "work_slots": "worker capacity",
    "work_waiters": "worker capacity",
    "usage_records": "metering; a gateway attempt still records",
    "agent_minute_ledger": "metering",
    "usage_month_rollups": "metering",
    "engagement_agent_budgets": "metering settings",
    "legal_holds": "governs retention; a hold on a locked file must be possible",
    "engagement_exports": "export.create is exempt after lock",
    "pilot_enrolments": "programme tracking",
    "engagement_members": "who may read the file changes after lock",
    "engagement_member_events": "the history of who may read",
    "engagement_contacts": "a client's people change after lock",
    "client_invitations": "portal access to a released file",
    "work_item_assignments": "who holds the item, not its content",
    "sync_runs": "a connector's bookkeeping",
    "connection_states": "a connector's bookkeeping",
    "reconnect_requests": "a connector's bookkeeping",
    "inbox_files": "the firm inbox; a file is filed elsewhere",
    "inbox_match_runs": "the firm inbox's matching",
}

ALLOWED_KINDS: Final[Mapping[str, tuple[ArchivedWriteKind, ...]]] = {
    "archive_additions": ("archive_addition",),
    "archive_addition_decisions": ("archive_addition",),
    "post_issuance_events": ("post_issuance",),
    "archives": ("retention_extend",),
    "evidence_versions": ("retention_extend", "destruction_tombstone"),
    "evidence_items": ("destruction_tombstone",),
}


def trigger_arguments(table: str) -> str:
    """The quoted kind list for this table's trigger: the only kinds it lets through."""
    return ", ".join(f"'{kind}'" for kind in ALLOWED_KINDS.get(table, ()))
