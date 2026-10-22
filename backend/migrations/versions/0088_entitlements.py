"""Plans and tenant entitlements (F-03-T28; ADR-148, P-28; DEC-55, DEC-19 D10).

Modules a firm may use are database rows, not feature flags: `plans` (global, platform) and
`tenant_entitlements` (one row per firm and module: attest, internal_audit, group_audit,
statements_studio, office_addins, insights; with seats and the agent-minute allowance). The app
reads entitlements under the firm's row-level security and writes none: plans and entitlements
are set by the operator console (G-04) and the scenario loader, never by a route or a migration
(content belongs in the database).

Revision ID: 0088
Revises: 0087
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None

MODULES = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', 'insights')"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE plans (
            code text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{1,40}$'),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute("REVOKE ALL ON plans FROM abacus_app")
    op.execute(
        f"""
        CREATE TABLE tenant_entitlements (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            module text NOT NULL CHECK (module IN {MODULES}),
            plan_code text NULL REFERENCES plans (code),
            enabled boolean NOT NULL DEFAULT true,
            seats integer NULL CHECK (seats >= 0),
            agent_minutes_allowance integer NULL CHECK (agent_minutes_allowance >= 0),
            valid_from date NOT NULL DEFAULT current_date,
            valid_to date NULL CHECK (valid_to IS NULL OR valid_to >= valid_from),
            set_by text NOT NULL CHECK (length(set_by) BETWEEN 1 AND 100),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, module)
        )
        """
    )
    tenant_table(op, "tenant_entitlements")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON tenant_entitlements FROM abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE tenant_entitlements")
    op.execute("DROP TABLE plans")
