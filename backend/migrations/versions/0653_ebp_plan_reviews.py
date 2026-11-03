"""A-05-T16 (A-05 §3 F2; DEC-2069): a plan review's chosen documents. Expand only.

`ebp_plan_reviews`: one row each time a person starts a provisions read on EBP-02 (review 1, 2,
...), naming the document versions it reads in order (the adoption agreement, the amendment when
in force, the SPD) and whether the 2024 amendment governs (twenty provisions, or eighteen). The
`ebp_provisions` mode reads the latest row. Insert-only; a person starts a review (actor CHECK).

Revision ID: 0653
Revises: 0652
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0653"
down_revision = "0652"
branch_labels = None
depends_on = None

COLUMNS = (
    "tenant_id",
    "engagement_id",
    "work_item_id",
    "workpaper_id",
    "review_no",
    "document_version_ids",
    "amendment_in_force",
    "started_by",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ebp_plan_reviews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            review_no integer NOT NULL CHECK (review_no >= 1),
            document_version_ids uuid[] NOT NULL
                CHECK (cardinality(document_version_ids) BETWEEN 1 AND 20),
            amendment_in_force boolean NOT NULL,
            started_by uuid NOT NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CONSTRAINT ebp_plan_reviews_by_a_person CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, workpaper_id, review_no),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ebp_plan_reviews_work_item ON ebp_plan_reviews (tenant_id, work_item_id)"
    )
    tenant_table(op, "ebp_plan_reviews")
    op.execute("REVOKE DELETE, TRUNCATE ON ebp_plan_reviews FROM abacus_app")
    insert_only(op, "ebp_plan_reviews")
    insert_columns(op, "ebp_plan_reviews", COLUMNS)


def downgrade() -> None:
    op.execute("DROP TABLE ebp_plan_reviews")
