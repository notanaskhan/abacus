"""R-01-T09: portal drops in the engagement inbox, for the code-rule sort (R-01 §4.2; DEC-58 a,
c, g; DEC-323).

`inbox_files` gains what a portal drop is:
- `channel` (`firm` by default, or `portal_drop`);
- `drop_batch_id`, `drop_binder_id` and `drop_key` (the client's `X-Drop-Batch`, the binder it
  was dropped on and its per-file `Idempotency-Key`), all three set exactly for a portal drop,
  one file per (dropper, batch, key) (`inbox_files_one_drop`: one person's key never blocks or
  answers for another's);
- `duplicate_of_version_id`: a drop with the same bytes as a version of the engagement is
  accepted and flagged for a person (DEC-58 g), never refused;
- `sort_outcome` (`rule_linked`, `waiting`; `assigned` and `discarded` later), which the app may
  set once, from NULL.
`inbox_files_one_waiting` (one waiting copy of the same bytes) now holds for the firm's channel
only: a client's duplicate drop is flagged, not refused.

Downgrade removes portal drops' rows first (a local database only; the columns go with them).

Revision ID: 0153
Revises: 0152
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0153"
down_revision = "0152"
branch_labels = None
depends_on = None

_V1_INSERT = (
    "tenant_id",
    "engagement_id",
    "file_name",
    "media_type",
    "size_bytes",
    "fingerprint",
    "storage_key",
    "storage_version_id",
    "uploaded_by",
    "uploaded_by_staff",
    "note",
)
_DROP_INSERT = (
    "channel",
    "drop_batch_id",
    "drop_binder_id",
    "drop_key",
    "duplicate_of_version_id",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE inbox_files
            ADD COLUMN channel text NOT NULL DEFAULT 'firm'
                CHECK (channel IN ('firm', 'portal_drop')),
            ADD COLUMN drop_batch_id uuid NULL,
            ADD COLUMN drop_binder_id uuid NULL,
            ADD COLUMN drop_key text NULL CHECK (length(drop_key) BETWEEN 1 AND 255),
            ADD COLUMN duplicate_of_version_id uuid NULL,
            ADD COLUMN sort_outcome text NULL
                CHECK (sort_outcome IN ('rule_linked', 'waiting', 'assigned', 'discarded')),
            ADD CONSTRAINT inbox_files_drop_shape CHECK (
                (channel = 'portal_drop') = (drop_batch_id IS NOT NULL)
                AND (drop_batch_id IS NULL) = (drop_binder_id IS NULL)
                AND (drop_batch_id IS NULL) = (drop_key IS NULL)
                AND (channel = 'portal_drop' OR sort_outcome IS NULL)
            ),
            ADD CONSTRAINT inbox_files_duplicate_of
                FOREIGN KEY (tenant_id, duplicate_of_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX inbox_files_one_drop ON inbox_files "
        "(tenant_id, drop_batch_id, uploaded_by, drop_key) WHERE channel = 'portal_drop'"
    )
    op.execute("CREATE INDEX inbox_files_by_batch ON inbox_files (tenant_id, drop_batch_id)")
    op.execute("DROP INDEX inbox_files_one_waiting")
    op.execute(
        "CREATE UNIQUE INDEX inbox_files_one_waiting ON inbox_files "
        "(tenant_id, engagement_id, fingerprint) WHERE status = 'waiting' AND channel = 'firm'"
    )
    insert_columns(op, "inbox_files", _V1_INSERT + _DROP_INSERT)
    op.execute("GRANT UPDATE (sort_outcome) ON inbox_files TO abacus_app")
    # The sort writes its outcome once: from NULL to a value, never back or over.
    op.execute(
        """
        CREATE FUNCTION inbox_files_sort_once() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.sort_outcome IS NOT NULL
               AND NEW.sort_outcome IS DISTINCT FROM OLD.sort_outcome THEN
                RAISE EXCEPTION 'a drop is sorted once' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER inbox_files_sort_once BEFORE UPDATE OF sort_outcome ON inbox_files "
        "FOR EACH ROW EXECUTE FUNCTION inbox_files_sort_once()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER inbox_files_sort_once ON inbox_files")
    op.execute("DROP FUNCTION inbox_files_sort_once()")
    op.execute("REVOKE UPDATE (sort_outcome) ON inbox_files FROM abacus_app")
    op.execute("DELETE FROM inbox_files WHERE channel = 'portal_drop'")
    insert_columns(op, "inbox_files", _V1_INSERT)
    op.execute("DROP INDEX inbox_files_one_waiting")
    op.execute(
        "CREATE UNIQUE INDEX inbox_files_one_waiting ON inbox_files "
        "(tenant_id, engagement_id, fingerprint) WHERE status = 'waiting'"
    )
    op.execute("DROP INDEX inbox_files_by_batch")
    op.execute("DROP INDEX inbox_files_one_drop")
    op.execute(
        "ALTER TABLE inbox_files DROP CONSTRAINT inbox_files_duplicate_of, "
        "DROP CONSTRAINT inbox_files_drop_shape, DROP COLUMN sort_outcome, "
        "DROP COLUMN duplicate_of_version_id, DROP COLUMN drop_key, DROP COLUMN drop_binder_id, "
        "DROP COLUMN drop_batch_id, DROP COLUMN channel"
    )
