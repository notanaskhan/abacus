"""Per-firm feature flag state (SPEC-011; ADR-089).

A firm's value for a registered flag, set by platform operators (audited); a firm without a row
gets the registry default. Unregistered flags' rows are inert.

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE feature_flag_states (
            tenant_id uuid NOT NULL,
            flag text NOT NULL CHECK (flag ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'),
            value text NOT NULL CHECK (length(value) BETWEEN 1 AND 100),
            set_by text NOT NULL CHECK (length(set_by) BETWEEN 1 AND 100),
            reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, flag)
        )
        """
    )
    tenant_table(op, "feature_flag_states")
    op.execute("REVOKE DELETE ON feature_flag_states FROM abacus_app")
    insert_columns(op, "feature_flag_states", ("tenant_id", "flag", "value", "set_by", "reason"))
    op.execute("REVOKE UPDATE ON feature_flag_states FROM abacus_app")
    op.execute("GRANT UPDATE (value, set_by, reason, set_at) ON feature_flag_states TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE feature_flag_states")
