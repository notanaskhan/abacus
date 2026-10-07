"""Budgets (SPEC-007; ADR-069): firm monthly budgets, spend indexes, and two SECURITY DEFINER
functions that read across firms but return only a number or identifiers: the platform's spend
today, and engagements whose last hour is anomalous.

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_FUNCTIONS = ("platform_spend_today()", "engagement_spend_anomalies(numeric, numeric)")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE budgets (
            tenant_id uuid PRIMARY KEY,
            monthly_soft_usd numeric(12, 2) NOT NULL CHECK (monthly_soft_usd > 0),
            monthly_hard_usd numeric(12, 2) NOT NULL CHECK (monthly_hard_usd > 0),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT budgets_soft_below_hard CHECK (monthly_soft_usd <= monthly_hard_usd),
            FOREIGN KEY (tenant_id, updated_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "budgets")
    op.execute("REVOKE DELETE ON budgets FROM abacus_app")
    insert_columns(
        op, "budgets", ("tenant_id", "monthly_soft_usd", "monthly_hard_usd", "updated_by")
    )
    op.execute("REVOKE UPDATE ON budgets FROM abacus_app")
    op.execute(
        "GRANT UPDATE (monthly_soft_usd, monthly_hard_usd, updated_by, updated_at) "
        "ON budgets TO abacus_app"
    )
    op.execute("CREATE INDEX usage_records_time ON usage_records (tenant_id, created_at)")
    op.execute(
        "CREATE INDEX usage_records_engagement_time "
        "ON usage_records (tenant_id, engagement_id, created_at)"
    )
    op.execute(
        """
        CREATE FUNCTION platform_spend_today() RETURNS numeric
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
            SELECT COALESCE(SUM(u.cost_usd), 0) FROM public.usage_records u
             WHERE u.created_at >= date_trunc('day', clock_timestamp())
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION engagement_spend_anomalies(p_multiple numeric, p_floor numeric)
        RETURNS TABLE (tenant_id uuid, engagement_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '30s'
        AS $$
            WITH hour AS (
                SELECT u.tenant_id, u.engagement_id, SUM(u.cost_usd) AS spent
                  FROM public.usage_records u
                 WHERE u.engagement_id IS NOT NULL
                   AND u.created_at >= clock_timestamp() - interval '1 hour'
                 GROUP BY 1, 2
            ), week AS (
                SELECT u.tenant_id, u.engagement_id, SUM(u.cost_usd) / 168.0 AS hourly
                  FROM public.usage_records u
                 WHERE u.engagement_id IS NOT NULL
                   AND u.created_at >= clock_timestamp() - interval '7 days'
                   AND u.created_at < clock_timestamp() - interval '1 hour'
                 GROUP BY 1, 2
            )
            SELECT h.tenant_id, h.engagement_id FROM hour h
              LEFT JOIN week w USING (tenant_id, engagement_id)
             WHERE h.spent > p_floor AND h.spent > p_multiple * COALESCE(w.hourly, 0)
        $$
        """
    )
    for signature in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")


def downgrade() -> None:
    for signature in _FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP INDEX usage_records_engagement_time")
    op.execute("DROP INDEX usage_records_time")
    op.execute("DROP TABLE budgets")
