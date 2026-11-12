"""T-05-T26 (S39; TASK-7518; T-05 §4.2 M5; C9): the tax form-line taxonomy on mapping sets.

- `mapping_sets.taxonomy_kind` ∈ {fs_line, tax_form_line} (default fs_line) and
  `mapping_sets.reference_set_version_id` (the C21 `tax_form_lines` version a tax set maps to).
  Exactly one target per kind: an `fs_line` set names its grouping set version, a
  `tax_form_line` set its reference set version (CHECK). `grouping_set_version_id` becomes
  nullable for that reason (a relaxation, expand-compatible).
- One set per trial balance per taxonomy (the 0079 `UNIQUE (tenant_id, trial_balance_id)` is
  replaced by `(tenant_id, trial_balance_id, taxonomy_kind)`): a partnership's TB carries its
  financial-statement set and its tax set side by side.
- `mapping_set_edits.form_line_key`: a tax set's row target. At most one target per row (CHECK);
  the trigger refuses a row whose target does not match its set's taxonomy. Edits stay a person's
  (`actor_kind = 'human'`, 0079): a mapping judgment is a proposal a person approves.

Revision ID: 0842
Revises: 0841
"""

from __future__ import annotations

from alembic import op

revision = "0842"
down_revision = "0841"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE mapping_sets
            ADD COLUMN taxonomy_kind text NOT NULL DEFAULT 'fs_line'
                CHECK (taxonomy_kind IN ('fs_line', 'tax_form_line')),
            ADD COLUMN reference_set_version_id uuid NULL,
            ALTER COLUMN grouping_set_version_id DROP NOT NULL,
            ADD CONSTRAINT mapping_sets_one_taxonomy_target CHECK (
                (taxonomy_kind = 'fs_line' AND grouping_set_version_id IS NOT NULL
                    AND reference_set_version_id IS NULL)
                OR (taxonomy_kind = 'tax_form_line' AND reference_set_version_id IS NOT NULL
                    AND grouping_set_version_id IS NULL))
        """
    )
    op.execute(
        "ALTER TABLE mapping_sets DROP CONSTRAINT mapping_sets_tenant_id_trial_balance_id_key"
    )
    op.execute(
        "ALTER TABLE mapping_sets ADD CONSTRAINT mapping_sets_one_per_taxonomy "
        "UNIQUE (tenant_id, trial_balance_id, taxonomy_kind)"
    )
    op.execute(
        "GRANT INSERT (taxonomy_kind, reference_set_version_id) ON mapping_sets TO abacus_app"
    )
    op.execute(
        """
        ALTER TABLE mapping_set_edits
            ADD COLUMN form_line_key text NULL
                CHECK (form_line_key ~ '^[A-Za-z0-9][A-Za-z0-9 .:()/-]{0,39}$'),
            ADD CONSTRAINT mapping_set_edits_one_target
                CHECK (fs_line_id IS NULL OR form_line_key IS NULL)
        """
    )
    op.execute("GRANT INSERT (form_line_key) ON mapping_set_edits TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION mapping_set_edit_taxonomy() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
        DECLARE
            kind text;
        BEGIN
            SELECT taxonomy_kind INTO kind FROM mapping_sets
             WHERE tenant_id = NEW.tenant_id AND id = NEW.mapping_set_id;
            IF kind = 'tax_form_line' AND NEW.fs_line_id IS NOT NULL THEN
                RAISE EXCEPTION 'a tax form-line set maps to form lines'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF kind = 'fs_line' AND NEW.form_line_key IS NOT NULL THEN
                RAISE EXCEPTION 'a financial-statement set maps to fs lines'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION mapping_set_edit_taxonomy() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER mapping_set_edits_taxonomy BEFORE INSERT ON mapping_set_edits "
        "FOR EACH ROW EXECUTE FUNCTION mapping_set_edit_taxonomy()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER mapping_set_edits_taxonomy ON mapping_set_edits")
    op.execute("DROP FUNCTION mapping_set_edit_taxonomy()")
    op.execute(
        "ALTER TABLE mapping_set_edits DROP CONSTRAINT mapping_set_edits_one_target, "
        "DROP COLUMN form_line_key"
    )
    op.execute("DELETE FROM mapping_sets WHERE taxonomy_kind = 'tax_form_line'")
    op.execute("ALTER TABLE mapping_sets DROP CONSTRAINT mapping_sets_one_per_taxonomy")
    op.execute(
        "ALTER TABLE mapping_sets ADD CONSTRAINT mapping_sets_tenant_id_trial_balance_id_key "
        "UNIQUE (tenant_id, trial_balance_id)"
    )
    op.execute(
        "ALTER TABLE mapping_sets DROP CONSTRAINT mapping_sets_one_taxonomy_target, "
        "DROP COLUMN reference_set_version_id, DROP COLUMN taxonomy_kind, "
        "ALTER COLUMN grouping_set_version_id SET NOT NULL"
    )
