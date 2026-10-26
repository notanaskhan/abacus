"""Tie-out checks: the issue link and the remaining A-02 §4.2 rules (A-02-T11; TASK-1337;
SPEC-333 AC-10; DEC-437). Expand-only.

0074 (SPEC-310) built `tie_out_checks` and `tie_out_check_versions` with A-02 §4.2's columns, the
citation CHECK (`expected IS NULL OR cardinality(citation_ids) > 0`) and the human-only CHECK.
What the row still asks for:

- **Issue link**: `tie_out_checks.issue_id`, `issue_linked_by`, `issue_linked_at` (all three
  or none), the issue in the same firm (composite FK to `issues`). The app may set them (column
  grant); the check's definition stays in its insert-only versions. A-02-T17 writes them.
- **A balanced check carries no expected value** (A-02 §4.2 `CHECK kind <> 'balanced' OR
  expected IS NULL`): `kind` lives on the check and `expected` on the version, so a BEFORE
  INSERT trigger on the versions enforces it.
- **Insert-only by trigger** (ADR-004, the "IO" of §4.2): 0074 revoked UPDATE and DELETE from
  the app; BEFORE UPDATE OR DELETE and BEFORE TRUNCATE triggers now refuse every role, as for
  `trial_balance_versions` (0149).

`down_revision` is 0172 on this branch (S10 wave B); the merge re-points it after the other
branches' migrations.

Revision ID: 0193
Revises: 0172
"""

from __future__ import annotations

from alembic import op

revision = "0193"
down_revision = "0172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tie_out_checks
            ADD COLUMN issue_id uuid NULL,
            ADD COLUMN issue_linked_by uuid NULL,
            ADD COLUMN issue_linked_at timestamptz NULL,
            ADD CONSTRAINT tie_out_checks_issue_link_whole CHECK (
                (issue_id IS NULL) = (issue_linked_by IS NULL)
                AND (issue_id IS NULL) = (issue_linked_at IS NULL)
            ),
            ADD CONSTRAINT tie_out_checks_issue_fk
                FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id)
        """
    )
    op.execute(
        "GRANT UPDATE (issue_id, issue_linked_by, issue_linked_at) ON tie_out_checks TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION tie_out_check_versions_rules() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.expected IS NOT NULL AND EXISTS (
                SELECT 1 FROM tie_out_checks c
                WHERE c.tenant_id = NEW.tenant_id AND c.id = NEW.check_id
                  AND c.kind = 'balanced'
            ) THEN
                RAISE EXCEPTION 'a balanced check has no expected value'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER tie_out_check_versions_rules BEFORE INSERT ON tie_out_check_versions "
        "FOR EACH ROW EXECUTE FUNCTION tie_out_check_versions_rules()"
    )
    op.execute(
        """
        CREATE FUNCTION tie_out_check_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tie-out check versions are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER tie_out_check_versions_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON tie_out_check_versions "
        "FOR EACH ROW EXECUTE FUNCTION tie_out_check_versions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER tie_out_check_versions_no_truncate "
        "BEFORE TRUNCATE ON tie_out_check_versions "
        "FOR EACH STATEMENT EXECUTE FUNCTION tie_out_check_versions_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER tie_out_check_versions_no_truncate ON tie_out_check_versions")
    op.execute("DROP TRIGGER tie_out_check_versions_no_update_or_delete ON tie_out_check_versions")
    op.execute("DROP FUNCTION tie_out_check_versions_immutable()")
    op.execute("DROP TRIGGER tie_out_check_versions_rules ON tie_out_check_versions")
    op.execute("DROP FUNCTION tie_out_check_versions_rules()")
    op.execute(
        "REVOKE UPDATE (issue_id, issue_linked_by, issue_linked_at) ON tie_out_checks "
        "FROM abacus_app"
    )
    op.execute(
        """
        ALTER TABLE tie_out_checks
            DROP CONSTRAINT tie_out_checks_issue_fk,
            DROP CONSTRAINT tie_out_checks_issue_link_whole,
            DROP COLUMN issue_linked_at,
            DROP COLUMN issue_linked_by,
            DROP COLUMN issue_id
        """
    )
