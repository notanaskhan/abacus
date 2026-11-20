"""T-06-T33 (S52; TASK-8831; SPEC-702 F1, AC-3; amber): a person's change to a fixed asset is a
ghost value until a reviewer decides it. `fixed_asset_change_requests` (the requested values and
the asset version they were made against) and `fixed_asset_change_decisions` (one per request:
approved or rejected, by someone other than the requester) are insert-only with forced RLS; the
asset row itself changes only on approval, through `fixed_asset_versions` (0952). Expand-only.

Revision ID: 0999
Revises: 0998
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0999"
down_revision = "0998"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE fixed_asset_change_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            asset_id uuid NOT NULL,
            expected_version integer NOT NULL CHECK (expected_version >= 1),
            change jsonb NOT NULL CHECK (jsonb_typeof(change) = 'object' AND change <> '{}'),
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            requested_by uuid NOT NULL
                CHECK (requested_by::text = current_setting('app.actor_id', true)),
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, asset_id) REFERENCES fixed_assets (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE fixed_asset_change_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            request_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
            reason text NULL CHECK (char_length(reason) <= 500),
            decided_by uuid NOT NULL
                CHECK (decided_by::text = current_setting('app.actor_id', true)),
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, request_id),
            CHECK (decision = 'approved' OR reason IS NOT NULL),
            FOREIGN KEY (tenant_id, request_id)
                REFERENCES fixed_asset_change_requests (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX fixed_asset_change_requests_asset ON fixed_asset_change_requests "
        "(tenant_id, asset_id, requested_at DESC)"
    )
    for table, columns in (
        ("fixed_asset_change_requests",
         ("tenant_id", "engagement_id", "work_item_id", "asset_id", "expected_version", "change",
          "citation_ids", "requested_by")),
        ("fixed_asset_change_decisions",
         ("tenant_id", "request_id", "decision", "reason", "decided_by")),
    ):  # fmt: skip
        tenant_table(op, table)
        insert_columns(op, table, columns)
        insert_only(op, table)


def downgrade() -> None:
    op.execute("DROP TABLE fixed_asset_change_decisions")
    op.execute("DROP TABLE fixed_asset_change_requests")
