"""Messages: the guarded outbound send path (SPEC-006; ADR-065, ADR-005).

Every message is recorded once, insert-only: `sent` (checked and handed to delivery) or
`blocked` (with its scope violations: kinds and identifiers, never text). The body is
confidential.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            channel text NOT NULL CHECK (channel IN ('email', 'portal')),
            recipient_ref text NOT NULL CHECK (length(recipient_ref) BETWEEN 1 AND 200),
            body text NOT NULL CHECK (length(body) BETWEEN 1 AND 20000),
            status text NOT NULL CHECK (status IN ('sent', 'blocked')),
            violations jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT messages_blocked_has_violations
                CHECK ((status = 'blocked') = (jsonb_array_length(violations) > 0)),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX messages_engagement ON messages (tenant_id, engagement_id)")
    tenant_table(op, "messages")
    insert_only(op, "messages")
    insert_columns(
        op,
        "messages",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "channel",
            "recipient_ref",
            "body",
            "status",
            "violations",
            "created_by",
        ),
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM messages) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: messages exist'; END IF; END $$"
    )
    op.execute("DROP TABLE messages")
