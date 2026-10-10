"""The engagement agent's pause switches and activity feed (SPEC-027; TASK-050).

`engagement_agents`: one row per engagement once its agent is paused or resumed (partner or
manager). `firms.agents_paused_*`: the firm-wide switch (firm administrator). `agent_activity`:
what happened automatically on an engagement, by which policy and why; insert-only, references
only (never client content): a count, and the person an action was for (the screening's
initiator, replayed on resume). One row per policy per source event, so redeliveries don't
repeat.

Revision ID: 0039
Revises: 0038
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engagement_agents (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            paused_at timestamptz NULL,
            paused_by uuid NULL,
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 300),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            CHECK ((paused_at IS NULL) = (paused_by IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE agent_activity (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            policy text NOT NULL CHECK (policy ~ '^P-[0-9]+$'),
            policy_version integer NOT NULL CHECK (policy_version >= 1),
            action text NOT NULL CHECK (action ~ '^[a-z_]+(\\.[a-z_]+)*$'),
            outcome text NOT NULL CHECK (outcome IN ('done', 'skipped', 'failed')),
            reason text NULL CHECK (reason ~ '^[a-z_]+$'),
            record_type text NULL CHECK (record_type ~ '^[a-z_]+$'),
            record_id uuid NULL,
            item_count integer NULL CHECK (item_count >= 0),
            for_user uuid NULL,
            source_event_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX agent_activity_once ON agent_activity "
        "(tenant_id, engagement_id, policy, source_event_id) WHERE source_event_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX agent_activity_feed ON agent_activity (tenant_id, engagement_id, created_at)"
    )
    for table in ("engagement_agents", "agent_activity"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON engagement_agents FROM abacus_app")
    insert_columns(
        op, "engagement_agents", ("tenant_id", "engagement_id", "paused_at", "paused_by", "reason")
    )
    op.execute(
        "GRANT UPDATE (paused_at, paused_by, reason, updated_at) "
        "ON engagement_agents TO abacus_app"
    )
    insert_only(op, "agent_activity")
    insert_columns(
        op,
        "agent_activity",
        (
            "tenant_id",
            "engagement_id",
            "policy",
            "policy_version",
            "action",
            "outcome",
            "reason",
            "record_type",
            "record_id",
            "item_count",
            "for_user",
            "source_event_id",
        ),
    )
    op.execute(
        "ALTER TABLE firms ADD COLUMN agents_paused_at timestamptz NULL, "
        "ADD COLUMN agents_paused_by uuid NULL, "
        "ADD CONSTRAINT firms_agents_paused CHECK "
        "((agents_paused_at IS NULL) = (agents_paused_by IS NULL))"
    )
    op.execute("GRANT UPDATE (agents_paused_at, agents_paused_by) ON firms TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (agents_paused_at, agents_paused_by) ON firms FROM abacus_app")
    op.execute(
        "ALTER TABLE firms DROP CONSTRAINT firms_agents_paused, "
        "DROP COLUMN agents_paused_at, DROP COLUMN agents_paused_by"
    )
    op.execute("DROP TABLE agent_activity")
    op.execute("DROP TABLE engagement_agents")
