"""The fieldwork flow (SPEC-040; TASK-100): sample approvals and row sign-offs.

- `selection_approvals` (insert-only): a manager's or the engagement partner's approval of one
  selection (once per selection). Selecting again makes a new, unapproved selection.
- `item_signoffs` (insert-only): a preparer's or reviewer's sign-off on one selected row, bound to
  the result it signed. It goes stale, never away, when a newer result is recorded.

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE item_results ADD CONSTRAINT item_results_by_id UNIQUE (tenant_id, id)")
    op.execute(
        """
        CREATE TABLE selection_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            selection_id uuid NOT NULL,
            approved_by uuid NOT NULL,
            note text NULL CHECK (length(note) BETWEEN 1 AND 1000),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT selection_approvals_once UNIQUE (tenant_id, selection_id),
            FOREIGN KEY (tenant_id, selection_id) REFERENCES selections (tenant_id, id)
        )
        """
    )
    tenant_table(op, "selection_approvals")
    op.execute("REVOKE UPDATE, DELETE ON selection_approvals FROM abacus_app")
    insert_columns(op, "selection_approvals", ("tenant_id", "selection_id", "approved_by", "note"))
    op.execute(
        """
        CREATE TABLE item_signoffs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            selected_item_id uuid NOT NULL,
            item_result_id uuid NOT NULL,
            level text NOT NULL CHECK (level IN ('prepared', 'reviewed')),
            signed_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT item_signoffs_once UNIQUE (tenant_id, item_result_id, level, signed_by),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id),
            FOREIGN KEY (tenant_id, item_result_id) REFERENCES item_results (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX item_signoffs_by_item ON item_signoffs (tenant_id, selected_item_id)")
    tenant_table(op, "item_signoffs")
    op.execute("REVOKE UPDATE, DELETE ON item_signoffs FROM abacus_app")
    insert_columns(
        op,
        "item_signoffs",
        ("tenant_id", "selected_item_id", "item_result_id", "level", "signed_by"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE item_signoffs")
    op.execute("DROP TABLE selection_approvals")
    op.execute("ALTER TABLE item_results DROP CONSTRAINT item_results_by_id")
