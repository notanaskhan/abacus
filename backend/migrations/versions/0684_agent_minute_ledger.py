"""P-10 M5: agent-minute metering (P-10-T06; P-10 §3.10, §4.2; ADR-148; SPEC-647).

`agent_minute_ledger` is insert-only, one row per run, written when `agent_run.completed` arrives:
integers summed by code, on the firm's usage month. `engagement_agent_budgets` holds minutes (1,500
by default, alert at 80%), not to be confused with `budgets` (USD safety) or the engagement's
hours. `usage_month_rollups` is rebuildable from the ledger.

Revision ID: 0684
Revises: 0683
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0684"
down_revision = "0683"
branch_labels = None
depends_on = None

_MONTH = "CHECK ({} ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])$')"
LEDGER = (
    "tenant_id", "usage_month", "run_id", "engagement_id", "work_item_ref", "service_line",
    "definition_id", "capability", "phase", "minutes", "agent_ms", "cost_usd",
)  # fmt: skip
BUDGETS = ("tenant_id", "engagement_id", "minutes_per_usage_month", "alert_pct")
ROLLUPS = (
    "tenant_id", "usage_month", "service_line", "engagement_id", "capability", "phase", "minutes",
    "cost_usd",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE agent_minute_ledger (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            usage_month text NOT NULL {_MONTH.format("usage_month")},
            run_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_ref text NULL CHECK (length(work_item_ref) <= 200),
            service_line text NOT NULL CHECK (length(service_line) BETWEEN 1 AND 40),
            definition_id uuid NULL,
            capability text NOT NULL CHECK (length(capability) BETWEEN 1 AND 80),
            phase text NULL CHECK (length(phase) <= 40),
            minutes integer NOT NULL CHECK (minutes >= 0),
            agent_ms bigint NOT NULL CHECK (agent_ms >= 0),
            cost_usd numeric(12, 4) NOT NULL CHECK (cost_usd >= 0),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, run_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX agent_minute_ledger_month ON agent_minute_ledger "
        "(tenant_id, usage_month, service_line)"
    )
    op.execute(
        """
        CREATE FUNCTION agent_minute_ledger_immutable() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent_minute_ledger is insert-only'
                USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION agent_minute_ledger_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER agent_minute_ledger_immutable BEFORE UPDATE OR DELETE "
        "ON agent_minute_ledger FOR EACH ROW EXECUTE FUNCTION agent_minute_ledger_immutable()"
    )
    op.execute(
        """
        CREATE TABLE engagement_agent_budgets (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            minutes_per_usage_month integer NOT NULL DEFAULT 1500
                CHECK (minutes_per_usage_month >= 0),
            alert_pct integer NOT NULL DEFAULT 80 CHECK (alert_pct BETWEEN 1 AND 100),
            PRIMARY KEY (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE usage_month_rollups (
            tenant_id uuid NOT NULL,
            usage_month text NOT NULL {_MONTH.format("usage_month")},
            service_line text NOT NULL,
            engagement_id uuid NULL,
            capability text NOT NULL,
            phase text NULL,
            minutes bigint NOT NULL CHECK (minutes >= 0),
            cost_usd numeric(14, 4) NOT NULL CHECK (cost_usd >= 0),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX usage_month_rollups_key ON usage_month_rollups (tenant_id, "
        "usage_month, service_line, engagement_id, capability, phase) NULLS NOT DISTINCT"
    )
    for table, columns in (
        ("agent_minute_ledger", LEDGER),
        ("engagement_agent_budgets", BUDGETS),
        ("usage_month_rollups", ROLLUPS),
    ):
        tenant_table(op, table)
        insert_columns(op, table, columns)
    insert_only(op, "agent_minute_ledger")
    op.execute(
        "GRANT UPDATE (minutes_per_usage_month, alert_pct) ON engagement_agent_budgets "
        "TO abacus_app"
    )
    op.execute("GRANT UPDATE (minutes, cost_usd) ON usage_month_rollups TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE usage_month_rollups")
    op.execute("DROP TABLE engagement_agent_budgets")
    op.execute("DROP TABLE agent_minute_ledger")
    op.execute("DROP FUNCTION agent_minute_ledger_immutable()")
