"""T-06-T39 (S52; TASK-8830; SPEC-702 F6; amber): `tax_handoff_landings`, the tax side's record
that a TB hand-off landed on its return (once per hand-off and per outbox event; insert-only,
forced RLS). The return's TB source is the handed-off Final snapshot, referenced by id (never
copied); the draft tax-line mapping seeded from the person's choices; the issues raised from the
toggled tax items. Nothing is written to the source engagement. Expand-only.

Revision ID: 0998
Revises: 0997
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0998"
down_revision = "0997"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tax_handoff_landings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            handoff_id uuid NOT NULL,
            event_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            source_snapshot_id uuid NOT NULL,
            draft_mapping jsonb NOT NULL CHECK (jsonb_typeof(draft_mapping) = 'array'),
            issue_ids uuid[] NOT NULL DEFAULT '{}',
            items_not_raised integer NOT NULL DEFAULT 0 CHECK (items_not_raised >= 0),
            landed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, handoff_id),
            UNIQUE (tenant_id, event_id),
            FOREIGN KEY (tenant_id, handoff_id) REFERENCES tb_handoffs (tenant_id, id),
            FOREIGN KEY (tenant_id, source_snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        "CREATE INDEX tax_handoff_landings_return ON tax_handoff_landings "
        "(tenant_id, return_id, version_no DESC)"
    )
    tenant_table(op, "tax_handoff_landings")
    insert_columns(
        op, "tax_handoff_landings",
        ("tenant_id", "return_id", "handoff_id", "event_id", "version_no", "source_snapshot_id",
         "draft_mapping", "issue_ids", "items_not_raised"),
    )  # fmt: skip
    insert_only(op, "tax_handoff_landings")


def downgrade() -> None:
    op.execute("DROP TABLE tax_handoff_landings")
