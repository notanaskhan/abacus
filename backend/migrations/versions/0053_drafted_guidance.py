"""Drafted guidance in the product (SPEC-035; TASK-073).

`request_items.guidance_source` gains `drafted` (approved drafter text). `guidance_draft_decisions`
(insert-only): a person approved (perhaps after editing) or discarded a draft, and for bulk
approval confirmed they read it. `firms.drafted_guidance_to_clients`: whether approved drafted
guidance is shown to clients (ADR-111; off by default; a firm admin sets it, D2).
`request_items.guidance_approved_by`: who approved drafted guidance (the firm's label).

Revision ID: 0053
Revises: 0052
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

_SOURCES = "('template', 'kind_default', 'firm', 'drafted')"


def upgrade() -> None:
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_guidance_source_check")
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_guidance_source_check "
        f"CHECK (guidance_source IN {_SOURCES})"
    )
    # Who approved drafted guidance, for the firm's label (requests can't read agents' tables).
    op.execute("ALTER TABLE request_items ADD COLUMN guidance_approved_by uuid NULL")
    op.execute("GRANT UPDATE (guidance_approved_by) ON request_items TO abacus_app")
    op.execute(
        """
        CREATE TABLE guidance_draft_decisions (
            tenant_id uuid NOT NULL,
            draft_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'discarded')),
            edited boolean NOT NULL DEFAULT false,
            confirmed_read boolean NOT NULL DEFAULT false,
            decided_by uuid NOT NULL REFERENCES users (id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, draft_id),
            FOREIGN KEY (tenant_id, draft_id) REFERENCES guidance_drafts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "guidance_draft_decisions")
    op.execute("REVOKE UPDATE, DELETE ON guidance_draft_decisions FROM abacus_app")
    insert_columns(
        op,
        "guidance_draft_decisions",
        ("tenant_id", "draft_id", "decision", "edited", "confirmed_read", "decided_by"),
    )
    op.execute(
        "ALTER TABLE firms ADD COLUMN drafted_guidance_to_clients boolean NOT NULL DEFAULT false"
    )
    op.execute("GRANT UPDATE (drafted_guidance_to_clients) ON firms TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (drafted_guidance_to_clients) ON firms FROM abacus_app")
    op.execute("ALTER TABLE firms DROP COLUMN drafted_guidance_to_clients")
    op.execute("DROP TABLE guidance_draft_decisions")
    op.execute("REVOKE UPDATE (guidance_approved_by) ON request_items FROM abacus_app")
    op.execute("ALTER TABLE request_items DROP COLUMN guidance_approved_by")
    op.execute(
        "UPDATE request_items SET guidance_source = 'firm' WHERE guidance_source = 'drafted'"
    )
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_guidance_source_check")
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_guidance_source_check "
        "CHECK (guidance_source IN ('template', 'kind_default', 'firm'))"
    )
