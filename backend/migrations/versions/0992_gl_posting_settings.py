"""C-02-T25 (S52; TASK-8810; ADR-344; red): `gl_posting_settings`, ADM-08b's memo prefix and
"Post as" label for QuickBooks Online posting, one row per firm, versioned. The two locked rows
("Post only human-approved batches", "Attest posting disabled") are code, not columns. Expand-only.

Revision ID: 0992
Revises: 0991
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0992"
down_revision = "0991"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE gl_posting_settings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            provider text NOT NULL DEFAULT 'quickbooks_online'
                CHECK (provider = 'quickbooks_online'),
            memo_prefix text NOT NULL CHECK (char_length(btrim(memo_prefix)) BETWEEN 1 AND 40),
            post_as text NOT NULL CHECK (char_length(btrim(post_as)) BETWEEN 1 AND 120),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, provider),
            FOREIGN KEY (tenant_id, updated_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "gl_posting_settings")
    insert_columns(
        op, "gl_posting_settings", ("tenant_id", "memo_prefix", "post_as", "updated_by")
    )
    op.execute("REVOKE UPDATE, DELETE ON gl_posting_settings FROM abacus_app")
    op.execute(
        "GRANT UPDATE (memo_prefix, post_as, version, updated_by, updated_at) "
        "ON gl_posting_settings TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE gl_posting_settings")
