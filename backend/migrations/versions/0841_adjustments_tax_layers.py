"""T-05-T25 (S39; TASK-7517; T-05 §4.2 M4; C8): the adjustments tax layers, expand-only.

- `proposed_entry_lines.account_scope` ∈ {book, tax_only} (default book): a tax-only account such
  as 4510-T exists only in the tax layer, so a tax-only line belongs to a `tje` entry.
- `proposed_entries` of kind `tje` ("TJE-n", numbered per work item like every kind) belong to a
  `tax_return` work item. Both rules are a trigger (they read another row), refusing with
  SQLSTATE 23514 before the row lands; the service refuses first with 422.
- The layers `atb`, `tje` and `ttb` stay computed, never stored (chapter 03 §3.8): ATB = UTB +
  AJE + RJE, TTB = ATB + TJE.

Revision ID: 0841
Revises: 0840
"""

from __future__ import annotations

from alembic import op

revision = "0841"
down_revision = "0840"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE proposed_entry_lines ADD COLUMN account_scope text NOT NULL DEFAULT 'book' "
        "CHECK (account_scope IN ('book', 'tax_only'))"
    )
    op.execute("GRANT INSERT (account_scope) ON proposed_entry_lines TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION proposed_entry_tax_scope() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
        DECLARE
            entry_kind text;
            item_kind text;
        BEGIN
            IF TG_TABLE_NAME = 'proposed_entries' THEN
                IF NEW.kind = 'tje' THEN
                    SELECT kind INTO item_kind FROM work_items
                     WHERE tenant_id = NEW.tenant_id AND id = NEW.work_item_id;
                    IF item_kind IS DISTINCT FROM 'tax_return' THEN
                        RAISE EXCEPTION 'a TJE belongs to a tax_return work item'
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.account_scope = 'tax_only' THEN
                SELECT kind INTO entry_kind FROM proposed_entries
                 WHERE tenant_id = NEW.tenant_id AND id = NEW.entry_id;
                IF entry_kind IS DISTINCT FROM 'tje' THEN
                    RAISE EXCEPTION 'a tax-only account belongs to a TJE'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION proposed_entry_tax_scope() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER proposed_entries_tax_scope BEFORE INSERT ON proposed_entries "
        "FOR EACH ROW EXECUTE FUNCTION proposed_entry_tax_scope()"
    )
    op.execute(
        "CREATE TRIGGER proposed_entry_lines_tax_scope BEFORE INSERT ON proposed_entry_lines "
        "FOR EACH ROW EXECUTE FUNCTION proposed_entry_tax_scope()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER proposed_entry_lines_tax_scope ON proposed_entry_lines")
    op.execute("DROP TRIGGER proposed_entries_tax_scope ON proposed_entries")
    op.execute("DROP FUNCTION proposed_entry_tax_scope()")
    op.execute("ALTER TABLE proposed_entry_lines DROP COLUMN account_scope")
