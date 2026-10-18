"""Data boundary for real firms, part 2 (SPEC-036; TASK-076).

- `firms.ai_client_data_at`, `_by`, `_material`: a firm admin's opt-in, against the provider terms
  entry's material fingerprint (Q4: a material change makes it lapse).
- `agent_stages` (insert-only, owner-written): an agent's stage for the firm (`shadow`, `live`,
  `off`); the newest row is the stage. The application role may only read it: stages change
  through the founder's operations command (D1), like `firms.synthetic`.
- `agent_runs.shadow`: the run started while its agent was in shadow for a real firm; its output
  is never shown (D2).
- `engagements.ai_excluded_at`, `_by`, `_reason`: the engagement partner switched AI off.

Revision ID: 0056
Revises: 0055
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE firms "
        "ADD COLUMN ai_client_data_at timestamptz NULL, "
        "ADD COLUMN ai_client_data_by uuid NULL, "
        "ADD COLUMN ai_client_data_material text NULL "
        "CHECK (ai_client_data_material ~ '^[0-9a-f]{64}$'), "
        "ADD CONSTRAINT firms_ai_client_data_whole CHECK ("
        "(ai_client_data_at IS NULL) = (ai_client_data_by IS NULL) AND "
        "(ai_client_data_at IS NULL) = (ai_client_data_material IS NULL))"
    )
    op.execute(
        "GRANT UPDATE (ai_client_data_at, ai_client_data_by, ai_client_data_material) "
        "ON firms TO abacus_app"
    )
    op.execute(
        """
        CREATE TABLE agent_stages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            agent_id text NOT NULL CHECK (agent_id ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'),
            stage text NOT NULL CHECK (stage IN ('shadow', 'live', 'off')),
            changed_by text NOT NULL CHECK (length(changed_by) BETWEEN 1 AND 100),
            note text NOT NULL CHECK (length(note) BETWEEN 1 AND 500),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        "CREATE INDEX agent_stages_newest ON agent_stages (tenant_id, agent_id, created_at DESC)"
    )
    tenant_table(op, "agent_stages")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON agent_stages FROM abacus_app")
    op.execute("ALTER TABLE agent_runs ADD COLUMN shadow boolean NOT NULL DEFAULT false")
    op.execute("GRANT INSERT (shadow) ON agent_runs TO abacus_app")
    op.execute(
        "ALTER TABLE engagements "
        "ADD COLUMN ai_excluded_at timestamptz NULL, "
        "ADD COLUMN ai_excluded_by uuid NULL, "
        "ADD COLUMN ai_excluded_reason text NULL "
        "CHECK (length(ai_excluded_reason) BETWEEN 1 AND 300), "
        "ADD CONSTRAINT engagements_ai_excluded_whole CHECK ("
        "(ai_excluded_at IS NULL) = (ai_excluded_by IS NULL) AND "
        "(ai_excluded_at IS NULL) = (ai_excluded_reason IS NULL))"
    )
    op.execute(
        "GRANT UPDATE (ai_excluded_at, ai_excluded_by, ai_excluded_reason) "
        "ON engagements TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (ai_excluded_at, ai_excluded_by, ai_excluded_reason) "
        "ON engagements FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE engagements DROP CONSTRAINT engagements_ai_excluded_whole, "
        "DROP COLUMN ai_excluded_reason, DROP COLUMN ai_excluded_by, DROP COLUMN ai_excluded_at"
    )
    op.execute("REVOKE INSERT (shadow) ON agent_runs FROM abacus_app")
    op.execute("ALTER TABLE agent_runs DROP COLUMN shadow")
    op.execute("DROP TABLE agent_stages")
    op.execute(
        "REVOKE UPDATE (ai_client_data_at, ai_client_data_by, ai_client_data_material) "
        "ON firms FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE firms DROP CONSTRAINT firms_ai_client_data_whole, "
        "DROP COLUMN ai_client_data_material, DROP COLUMN ai_client_data_by, "
        "DROP COLUMN ai_client_data_at"
    )
