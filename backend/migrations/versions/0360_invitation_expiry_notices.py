"""P-07-T47's producer for `invitation_expiring` (P-07 §4.8; DEC-540, DEC-1000).

- `invitation_expiry_notices` (new, identity, insert-only): one row per client invitation and
  expiry once the firm's admins were told, on day 12 of its 14 days, that it is about to lapse
  (the hourly identity pass's idempotence). The expiry is part of the key, so a resent or
  extended invitation is noticed again before its new end.

Revision ID: 0360
Revises: 0291
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0360"
down_revision = "0291"
branch_labels = None
depends_on = None

_TABLE = "invitation_expiry_notices"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {_TABLE} (
            tenant_id uuid NOT NULL,
            invitation_id uuid NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, invitation_id, expires_at),
            FOREIGN KEY (tenant_id, invitation_id) REFERENCES client_invitations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {_TABLE}_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{_TABLE} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {_TABLE}_immutable BEFORE UPDATE OR DELETE ON {_TABLE} "
        f"FOR EACH ROW EXECUTE FUNCTION {_TABLE}_immutable()"
    )
    tenant_table(op, _TABLE)
    op.execute(f"REVOKE UPDATE, DELETE ON {_TABLE} FROM abacus_app")
    insert_columns(op, _TABLE, ("tenant_id", "invitation_id", "expires_at"))


def downgrade() -> None:
    op.execute(f"DROP TABLE {_TABLE}")
    op.execute(f"DROP FUNCTION {_TABLE}_immutable()")
