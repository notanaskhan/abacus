"""Comments (SPEC-032; TASK-062; ADR-109).

`comments`: one per comment on a request item's thread or one of its evidence versions' threads;
the text is sealed per tenant (`kernel.crypto`, Restricted) and never stored in the clear. A
client's comment is always shared. `comment_mentions`, `comment_redactions`: who was mentioned,
and the one redaction a comment may get. All three insert-only: nothing is edited or deleted.
`comment_reads`: each person's last-read time per thread, the only row the app updates.

Revision ID: 0048
Revises: 0047
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

_INSERT_ONLY = ("comments", "comment_mentions", "comment_redactions")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE comments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            author_user_id uuid NOT NULL REFERENCES users (id),
            author_side text NOT NULL CHECK (author_side IN ('firm', 'client')),
            visibility text NOT NULL CHECK (visibility IN ('internal', 'shared')),
            body_sealed bytea NOT NULL,
            body_fingerprint text NOT NULL CHECK (body_fingerprint ~ '^[0-9a-f]{64}$'),
            corrects_comment_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT comments_client_shared
                CHECK (author_side = 'firm' OR visibility = 'shared'),
            FOREIGN KEY (tenant_id, engagement_id, request_item_id)
                REFERENCES request_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, corrects_comment_id) REFERENCES comments (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX comments_thread ON comments "
        "(tenant_id, request_item_id, evidence_version_id, created_at)"
    )
    op.execute(
        """
        CREATE TABLE comment_mentions (
            tenant_id uuid NOT NULL,
            comment_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            PRIMARY KEY (tenant_id, comment_id, user_id),
            FOREIGN KEY (tenant_id, comment_id) REFERENCES comments (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE comment_redactions (
            tenant_id uuid NOT NULL,
            comment_id uuid NOT NULL,
            redacted_by uuid NOT NULL REFERENCES users (id),
            reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, comment_id),
            FOREIGN KEY (tenant_id, comment_id) REFERENCES comments (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE comment_reads (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            request_item_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            last_read_at timestamptz NOT NULL,
            CONSTRAINT comment_reads_once UNIQUE NULLS NOT DISTINCT
                (tenant_id, user_id, request_item_id, evidence_version_id)
        )
        """
    )
    for table in (*_INSERT_ONLY, "comment_reads"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "comments",
        (
            "id",  # the service sets it, to link mentions in the same unit of work
            "tenant_id",
            "engagement_id",
            "request_item_id",
            "evidence_version_id",
            "author_user_id",
            "author_side",
            "visibility",
            "body_sealed",
            "body_fingerprint",
            "corrects_comment_id",
        ),
    )
    insert_columns(op, "comment_mentions", ("tenant_id", "comment_id", "user_id"))
    insert_columns(op, "comment_redactions", ("tenant_id", "comment_id", "redacted_by", "reason"))
    insert_columns(
        op,
        "comment_reads",
        ("tenant_id", "user_id", "request_item_id", "evidence_version_id", "last_read_at"),
    )
    op.execute("GRANT UPDATE (last_read_at) ON comment_reads TO abacus_app")


def downgrade() -> None:
    for table in ("comment_reads", "comment_redactions", "comment_mentions", "comments"):
        op.execute(f"DROP TABLE {table}")
