"""S35 follow-up (TASK-6741; DEC-3308): an archive addition after lock carries its document as a
new evidence version. `archived_guard()` on `evidence_items` and `evidence_versions` now also lets
`archived_write = archive_addition` through, which only `archive_additions` sets (ARCHIVE-001);
every other write to a locked file's evidence is still refused (`AB409`). The app may also supply
an addition's `id` (the addition manifest names the id before the row exists; the insert was
refused without it). The A-07 archive tables, the AU-C 260 send and the report versions stamp
with `abacus_now()`, as `archives` does: the wall clock for a real firm, a synthetic firm's
business time, so the demo's Jan 15 addition does not read as the day of the load and a fixture
export is the same on every load. Triggers, one grant and defaults; no data.

Revision ID: 0814
Revises: 0813
"""

from __future__ import annotations

from alembic import op

revision = "0814"
down_revision = "0813"
branch_labels = None
depends_on = None

# The kinds each table admits, frozen here (the kernel's ALLOWED_KINDS moves on; this does not).
_AFTER = {
    "evidence_items": "'destruction_tombstone', 'archive_addition'",
    "evidence_versions": "'retention_extend', 'destruction_tombstone', 'archive_addition'",
}
_BEFORE = {
    "evidence_items": "'destruction_tombstone'",
    "evidence_versions": "'retention_extend', 'destruction_tombstone'",
}


def _replace(kinds: dict[str, str]) -> None:
    for table, args in kinds.items():
        op.execute(f"DROP TRIGGER IF EXISTS archived_guard ON {table}")
        op.execute(
            f"CREATE TRIGGER archived_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION archived_guard({args})"
        )


_STAMPED = (
    ("archive_additions", "created_at"),
    ("archive_addition_decisions", "created_at"),
    ("archive_lock_decisions", "created_at"),
    ("archive_manifests", "created_at"),
    ("archive_binder_indexes", "created_at"),
    # The AU-C 260 letter's send and the report's versions (AUD-22, AUD-23): a 10:05 export read
    # the load's wall clock here, so no two exports matched (S35 follow-up, item 4).
    ("governance_communication_sends", "sent_at"),
    ("audit_report_versions", "created_at"),
)


def upgrade() -> None:
    _replace(_AFTER)
    op.execute("GRANT INSERT (id) ON archive_additions TO abacus_app")
    for table, column in _STAMPED:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT abacus_now()")


def downgrade() -> None:
    for table, column in _STAMPED:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT clock_timestamp()")
    op.execute("REVOKE INSERT (id) ON archive_additions FROM abacus_app")
    _replace(_BEFORE)
