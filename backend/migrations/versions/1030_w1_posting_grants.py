"""W1 posting's two missing column grants (CV-2, TASK-9001; ED-340; DEC-6006).

0950 (C-02-T18) widened `pe_posting_target` to allow `'client_ledger'` and made W1 stamp it when a
posting batch takes an entry (`posting._STAMP`) and clear it on undo, but `posting_target` was left
out of 0950's column-level `GRANT UPDATE` (0896 had granted it for INSERT only, for eliminations).
So `abacus_app` could not create any posting batch: `permission denied for table proposed_entries`
(500). No test had run a batch on the migrated database; CV-2's W1 suite found it.

The same omission held `posting_batches.approval_grant_id`: 0950 granted it for INSERT, but
`create_batch` issues the grant after the batch row exists (the grant names the batch as its
subject) and sets it with an UPDATE, which `abacus_app` could not make either.

This grants UPDATE on those two columns, and makes `approval_grant_id` set-once: NULL to a grant,
never re-pointed or cleared (a trigger), so the column-level grant adds no way to move a batch onto
another approval. The CHECKs 0950 added still bound what it may hold
(`pe_posting_target`, `pe_target_kind`, the attest and dormant-posting checks), and the row stays
under RLS and the entry lock trigger.
"""

from __future__ import annotations

from alembic import op

revision = "1030"
down_revision = "1019"
branch_labels = None
depends_on = None


_SET_ONCE = """
CREATE FUNCTION posting_batches_grant_set_once() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF OLD.approval_grant_id IS NOT NULL
       AND NEW.approval_grant_id IS DISTINCT FROM OLD.approval_grant_id THEN
        RAISE EXCEPTION 'approval_grant_set_once' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.execute("GRANT UPDATE (posting_target) ON proposed_entries TO abacus_app")
    op.execute("GRANT UPDATE (approval_grant_id) ON posting_batches TO abacus_app")
    op.execute(_SET_ONCE)
    op.execute("REVOKE ALL ON FUNCTION posting_batches_grant_set_once() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER posting_batches_grant_set_once BEFORE UPDATE OF approval_grant_id "
        "ON posting_batches FOR EACH ROW EXECUTE FUNCTION posting_batches_grant_set_once()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER posting_batches_grant_set_once ON posting_batches")
    op.execute("DROP FUNCTION posting_batches_grant_set_once()")
    op.execute("REVOKE UPDATE (approval_grant_id) ON posting_batches FROM abacus_app")
    op.execute("REVOKE UPDATE (posting_target) ON proposed_entries FROM abacus_app")
