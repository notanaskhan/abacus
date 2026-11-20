"""Q-05-T16 part 1 (S52; TASK-8820; SPEC-711 AC-7, AC-8; OQ-6; red): `inspection_access_grants`.

A monitoring inspector's time-boxed, read-only access to the engagements an inspection covers
(identity owns it; authorise and visible() read it as the `inspector` relationship). Granted when
the inspection is planned, expiring at the conclusion or the due date + 30 days, revocable; a
nightly sweep ends expired grants. Walls still override (authorise checks walls first). Forced RLS,
insert-only but for the revocation columns. Expand-only.

Revision ID: 0995
Revises: 0994
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0995"
down_revision = "0994"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE inspection_access_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            inspection_id uuid NOT NULL,
            inspector_user_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            granted_by uuid NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz NULL,
            revoked_by text NULL CHECK (char_length(revoked_by) BETWEEN 1 AND 100),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, inspection_id, inspector_user_id, engagement_id),
            CHECK (expires_at > granted_at),
            CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
            FOREIGN KEY (tenant_id, inspector_user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, granted_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX inspection_access_grants_live ON inspection_access_grants "
        "(tenant_id, inspector_user_id, engagement_id) WHERE revoked_at IS NULL"
    )
    tenant_table(op, "inspection_access_grants")
    insert_columns(
        op,
        "inspection_access_grants",
        ("tenant_id", "inspection_id", "inspector_user_id", "engagement_id", "granted_by",
         "expires_at"),
    )  # fmt: skip
    op.execute("REVOKE UPDATE, DELETE ON inspection_access_grants FROM abacus_app")
    op.execute("GRANT UPDATE (revoked_at, revoked_by) ON inspection_access_grants TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE inspection_access_grants")
