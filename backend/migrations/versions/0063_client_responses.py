"""The client's responses on requests (SPEC-042; TASK-106).

- `client_item_responses` (insert-only): a client saying a request doesn't apply (with a reason),
  or withdrawing that; the newest counts. The request's status never changes by it (ADR-005).
- `client_list_done` (insert-only): the client admin marking their list done.

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE client_item_responses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('not_applicable', 'withdrawn')),
            reason text NULL CHECK (reason IN ('not_this_year', 'sent_another_way', 'dont_have')),
            note text NULL CHECK (length(note) BETWEEN 1 AND 500),
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((kind = 'not_applicable') = (reason IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX client_item_responses_by_item "
        "ON client_item_responses (tenant_id, request_item_id, created_at DESC)"
    )
    tenant_table(op, "client_item_responses")
    op.execute("REVOKE UPDATE, DELETE ON client_item_responses FROM abacus_app")
    insert_columns(
        op,
        "client_item_responses",
        ("tenant_id", "engagement_id", "request_item_id", "kind", "reason", "note", "by_user"),
    )
    op.execute(
        """
        CREATE TABLE client_list_done (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    tenant_table(op, "client_list_done")
    op.execute("REVOKE UPDATE, DELETE ON client_list_done FROM abacus_app")
    insert_columns(op, "client_list_done", ("tenant_id", "engagement_id", "by_user"))


def downgrade() -> None:
    op.execute("DROP TABLE client_list_done")
    op.execute("DROP TABLE client_item_responses")
