"""Evaluation runs (SPEC-005 AC-13, AC-14; TASK-020 design §7, D3).

`eval_runs` holds one row per run of an agent's evaluation suite: what ran (agent, suite and
prompt versions, model, tier, fake or real), its outcome and reasons, metrics, calibration and
cost. `eval_case_results` holds each case attempt's grader outcomes and cost. Both are platform
tables written only by the evaluation tooling (the owner role), with no app privileges and row-
level security enabled with no policy, like the work slot ledger (TASK-018 D3). `tenant_id` is
reserved for firm-scoped cases (ADR-081) and is null for synthetic runs.

A run is immutable once finished: the only update allowed is `running` to a final state, and
nothing that identifies the run changes. Case results are insert-only, and only while their run
is `running`. The gateway asks `eval_eligible(agent, tier, model, prompt version, suite
version)`, a SECURITY DEFINER function the app may execute: true only if the latest finished
full-suite run on a real (non-fake) model for that key passed. A later failed, `aborted_cost` or
`errored` run revokes it; fast-subset and fake runs never count.

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_TABLES = ("eval_case_results", "eval_runs")
_ELIGIBLE = "eval_eligible(text, text, text, text, integer)"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE eval_runs (
            id uuid PRIMARY KEY,
            tenant_id uuid NULL,
            agent_id text NOT NULL CHECK (agent_id ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'),
            suite_version integer NOT NULL CHECK (suite_version >= 1),
            prompt_version text NOT NULL CHECK (length(prompt_version) BETWEEN 1 AND 100),
            model text NOT NULL CHECK (length(model) BETWEEN 1 AND 100),
            tier text NOT NULL CHECK (tier IN ('small', 'medium', 'large')),
            subset text NOT NULL CHECK (subset IN ('fast', 'full')),
            fake boolean NOT NULL,
            route text NOT NULL CHECK (length(route) BETWEEN 1 AND 100),
            seeds jsonb NOT NULL DEFAULT '{}',
            status text NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'passed', 'failed', 'aborted_cost', 'errored')),
            reasons text[] NOT NULL DEFAULT '{}',
            metrics jsonb NOT NULL DEFAULT '{}',
            calibration jsonb NOT NULL DEFAULT '{}',
            total_cost_usd numeric(12, 6) NOT NULL DEFAULT 0 CHECK (total_cost_usd >= 0),
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            finished_at timestamptz NULL,
            CONSTRAINT eval_runs_finished CHECK ((status = 'running') = (finished_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX eval_runs_key ON eval_runs "
        "(agent_id, tier, model, prompt_version, finished_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE eval_case_results (
            run_id uuid NOT NULL REFERENCES eval_runs (id),
            case_id text NOT NULL CHECK (case_id ~ '^[a-z][a-z0-9_]{0,99}$'),
            attempt integer NOT NULL CHECK (attempt >= 1),
            passed boolean NOT NULL,
            graders jsonb NOT NULL,
            cost_usd numeric(12, 6) NOT NULL CHECK (cost_usd >= 0),
            PRIMARY KEY (run_id, case_id, attempt)
        )
        """
    )
    for table in _TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # A run changes once: running → a final state, nothing else; it is never deleted.
    op.execute(
        """
        CREATE FUNCTION eval_runs_finish_once() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' OR OLD.status <> 'running' OR NEW.status = 'running'
               OR NEW.id <> OLD.id OR NEW.agent_id <> OLD.agent_id
               OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.suite_version <> OLD.suite_version
               OR NEW.prompt_version <> OLD.prompt_version OR NEW.model <> OLD.model
               OR NEW.tier <> OLD.tier OR NEW.subset <> OLD.subset OR NEW.fake <> OLD.fake
               OR NEW.route <> OLD.route OR NEW.seeds <> OLD.seeds
               OR NEW.started_at <> OLD.started_at THEN
                RAISE EXCEPTION 'evaluation runs are immutable once finished'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER eval_runs_finish_once BEFORE UPDATE OR DELETE ON eval_runs "
        "FOR EACH ROW EXECUTE FUNCTION eval_runs_finish_once()"
    )
    op.execute(
        """
        CREATE FUNCTION eval_case_results_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'evaluation case results are immutable'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER eval_case_results_no_update_or_delete "
        "BEFORE UPDATE OR DELETE ON eval_case_results "
        "FOR EACH ROW EXECUTE FUNCTION eval_case_results_immutable()"
    )
    op.execute(
        "CREATE TRIGGER eval_case_results_no_truncate BEFORE TRUNCATE ON eval_case_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION eval_case_results_immutable()"
    )
    # A case result belongs to a run still in progress: a finished run gains nothing.
    op.execute(
        """
        CREATE FUNCTION eval_case_results_while_running() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM eval_runs WHERE id = NEW.run_id AND status = 'running'
            ) THEN
                RAISE EXCEPTION 'evaluation case results are added only while the run is running'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER eval_case_results_while_running BEFORE INSERT ON eval_case_results "
        "FOR EACH ROW EXECUTE FUNCTION eval_case_results_while_running()"
    )
    op.execute(
        "CREATE TRIGGER eval_runs_no_truncate BEFORE TRUNCATE ON eval_runs "
        "FOR EACH STATEMENT EXECUTE FUNCTION eval_case_results_immutable()"
    )
    op.execute(
        """
        CREATE FUNCTION eval_eligible(
            p_agent_id text, p_tier text, p_model text, p_prompt_version text,
            p_suite_version integer
        ) RETURNS boolean
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
                   AND r.status <> 'running'
                 ORDER BY r.finished_at DESC, r.id DESC
                 LIMIT 1
            ), false)
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_ELIGIBLE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ELIGIBLE} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_ELIGIBLE}")
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION eval_case_results_immutable()")
    op.execute("DROP FUNCTION eval_case_results_while_running()")
    op.execute("DROP FUNCTION eval_runs_finish_once()")
