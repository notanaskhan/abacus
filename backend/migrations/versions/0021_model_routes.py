"""Model routes (SPEC-010; ADR-073, ADR-070).

Usage records name the route that answered (`fake`, `direct`, `bedrock`); existing rows were all
on the fake route. Evaluation eligibility is per route: `eval_eligible` gains the route, and the
signature without it is dropped (ADR-073: an evaluation run per allowed route and model).

Revision ID: 0021
Revises: 0020
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_OLD = "eval_eligible(text, text, text, text, integer)"
_NEW = "eval_eligible(text, text, text, text, text, integer)"
_BODY = """
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
            SELECT coalesce((
                SELECT r.status = 'passed'
                  FROM public.eval_runs r
                 WHERE r.agent_id = p_agent_id AND r.tier = p_tier AND r.model = p_model
                   AND r.prompt_version = p_prompt_version
                   AND r.suite_version = p_suite_version
                   AND r.subset = 'full' AND r.tenant_id IS NULL AND NOT r.fake
                   AND r.status <> 'running'{route}
                 ORDER BY r.finished_at DESC, r.id DESC
                 LIMIT 1
            ), false)
        $$
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usage_records ADD COLUMN route text NOT NULL DEFAULT 'fake' "
        "CHECK (route IN ('fake', 'direct', 'bedrock'))"
    )
    op.execute("GRANT INSERT (route) ON usage_records TO abacus_app")
    op.execute(f"DROP FUNCTION {_OLD}")
    op.execute(
        "CREATE FUNCTION eval_eligible(p_agent_id text, p_route text, p_tier text, "
        "p_model text, p_prompt_version text, p_suite_version integer) RETURNS boolean"
        + _BODY.format(route="\n                   AND r.route = p_route")
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_NEW} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_NEW} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_NEW}")
    op.execute(
        "CREATE FUNCTION eval_eligible(p_agent_id text, p_tier text, p_model text, "
        "p_prompt_version text, p_suite_version integer) RETURNS boolean" + _BODY.format(route="")
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_OLD} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_OLD} TO abacus_app")
    op.execute("REVOKE INSERT (route) ON usage_records FROM abacus_app")
    op.execute("ALTER TABLE usage_records DROP COLUMN route")
