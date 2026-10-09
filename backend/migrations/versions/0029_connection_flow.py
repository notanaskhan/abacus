"""The client connection flow (SPEC-020; TASK-036).

- `connection_states`: one per started flow, single-use and short-lived, the state stored only as
  its SHA-256, bound to the user, engagement and client entity.
- `connection_secrets`: a connection's provider credentials, sealed with the tenant's key
  (ADR-035); deleted on revoke, never updated.
- `connections`: the app now creates them (`connection.create`, a client admin), records health
  checks and revocation; one live connection (active or needing attention) per client entity.

Revision ID: 0029
Revises: 0028
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE connections
            DROP CONSTRAINT connections_status_check,
            ADD CONSTRAINT connections_status_check
                CHECK (status IN ('active', 'needs_attention', 'revoked')),
            ADD COLUMN last_checked_at timestamptz NULL,
            ADD COLUMN last_check_ok boolean NULL,
            ADD COLUMN revoked_at timestamptz NULL,
            ADD COLUMN revoked_by text NULL CHECK (length(revoked_by) BETWEEN 1 AND 200),
            ADD CONSTRAINT connections_revoked_has_when
                CHECK ((status = 'revoked') = (revoked_at IS NOT NULL))
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX connections_one_live ON connections (tenant_id, client_entity_id) "
        "WHERE status <> 'revoked'"
    )
    insert_columns(
        op,
        "connections",
        ("id", "tenant_id", "client_entity_id", "provider", "scopes", "created_by"),
    )
    op.execute(
        "GRANT UPDATE (status, last_checked_at, last_check_ok, revoked_at, revoked_by) "
        "ON connections TO abacus_app"
    )
    op.execute(
        """
        CREATE TABLE connection_states (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            user_id uuid NOT NULL,
            provider text NOT NULL CHECK (provider IN ('fake')),
            state_hash text NOT NULL UNIQUE CHECK (state_hash ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            used_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id),
            CHECK (expires_at > created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE connection_secrets (
            connection_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            sealed bytea NOT NULL CHECK (octet_length(sealed) BETWEEN 1 AND 65536),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id)
        )
        """
    )
    for table in ("connection_states", "connection_secrets"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON connection_states FROM abacus_app")
    insert_columns(
        op,
        "connection_states",
        (
            "tenant_id",
            "engagement_id",
            "client_entity_id",
            "user_id",
            "provider",
            "state_hash",
            "expires_at",
        ),
    )
    op.execute("GRANT UPDATE (used_at) ON connection_states TO abacus_app")
    op.execute("REVOKE UPDATE ON connection_secrets FROM abacus_app")
    insert_columns(op, "connection_secrets", ("connection_id", "tenant_id", "sealed"))


def downgrade() -> None:
    op.execute("DROP TABLE connection_secrets")
    op.execute("DROP TABLE connection_states")
    op.execute(
        "REVOKE UPDATE (status, last_checked_at, last_check_ok, revoked_at, revoked_by) "
        "ON connections FROM abacus_app"
    )
    op.execute("REVOKE INSERT ON connections FROM abacus_app")
    op.execute("GRANT UPDATE (status) ON connections TO abacus_app")
    op.execute("DROP INDEX connections_one_live")
    op.execute(
        """
        ALTER TABLE connections
            DROP CONSTRAINT connections_revoked_has_when,
            DROP COLUMN revoked_by,
            DROP COLUMN revoked_at,
            DROP COLUMN last_check_ok,
            DROP COLUMN last_checked_at,
            DROP CONSTRAINT connections_status_check,
            ADD CONSTRAINT connections_status_check CHECK (status IN ('active', 'revoked'))
        """
    )
