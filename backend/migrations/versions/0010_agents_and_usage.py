"""Agent runs, screening results and model usage records (TASK-011 design §1, §2, §6).

- `agent_runs` records each agent's run: what it was allowed (task scope), on whose behalf
  (initiator, ADR-025), from which event, and what it produced. Forward-only like sync runs.
- `screening_results` are proposals by agents (ADR-005): insert-only, `created_by_kind` is always
  `agent` (AC-14).
- `usage_records`: one row per model call, attributed to firm, engagement, agent, run and prompt
  version (AC-16, ADR-070). Insert-only.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            agent_id text NOT NULL CHECK (agent_id ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'),
            spec_version integer NOT NULL CHECK (spec_version >= 1),
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NULL,
            initiator_user_id uuid NOT NULL,
            source_event_id uuid NULL,
            task_scope text[] NOT NULL,
            status text NOT NULL DEFAULT 'running'
                CHECK (status IN ('running', 'completed', 'escalated', 'failed')),
            context_hash text NULL CHECK (context_hash ~ '^[0-9a-f]{64}$'),
            output jsonb NULL,
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            finished_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, id),
            CONSTRAINT agent_runs_finished CHECK ((status = 'running') = (finished_at IS NULL)),
            CONSTRAINT agent_runs_failure_code
                CHECK ((status = 'failed') = (failure_code IS NOT NULL)),
            -- One agent run per agent and triggering event (at-least-once delivery, ADR-018).
            CONSTRAINT agent_runs_once_per_event UNIQUE (tenant_id, agent_id, source_event_id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, initiator_user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE screening_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            action text NOT NULL CHECK (action IN ('ready_for_review', 'needs_revision')),
            confidence numeric(4, 3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
            citations jsonb NOT NULL,
            unverified jsonb NOT NULL,
            created_by_kind text NOT NULL DEFAULT 'agent' CHECK (created_by_kind = 'agent'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT screening_results_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, engagement_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE usage_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            agent_id text NOT NULL,
            agent_run_id uuid NULL,
            prompt_id text NOT NULL CHECK (length(prompt_id) BETWEEN 1 AND 100),
            prompt_version text NOT NULL CHECK (length(prompt_version) BETWEEN 1 AND 20),
            model text NOT NULL CHECK (length(model) BETWEEN 1 AND 100),
            tier text NOT NULL CHECK (tier IN ('small', 'medium', 'large')),
            input_tokens integer NOT NULL CHECK (input_tokens >= 0),
            output_tokens integer NOT NULL CHECK (output_tokens >= 0),
            cost_usd numeric(12, 6) NOT NULL CHECK (cost_usd >= 0),
            outcome text NOT NULL CHECK (
                outcome IN ('ok', 'invalid', 'repaired', 'budget_refused', 'provider_error')
            ),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, agent_run_id) REFERENCES agent_runs (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX usage_records_engagement ON usage_records (tenant_id, engagement_id)")
    op.execute(
        "CREATE INDEX screening_results_version "
        "ON screening_results (tenant_id, evidence_version_id)"
    )
    for table in ("agent_runs", "screening_results", "usage_records"):
        tenant_table(op, table)

    op.execute("REVOKE UPDATE, DELETE ON agent_runs FROM abacus_app")
    insert_columns(
        op,
        "agent_runs",
        (
            "id",
            "tenant_id",
            "agent_id",
            "spec_version",
            "engagement_id",
            "evidence_version_id",
            "initiator_user_id",
            "source_event_id",
            "task_scope",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, context_hash, output, failure_code, finished_at) "
        "ON agent_runs TO abacus_app"
    )
    insert_only(op, "screening_results")
    insert_columns(
        op,
        "screening_results",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "evidence_version_id",
            "agent_run_id",
            "action",
            "confidence",
            "rationale",
            "citations",
            "unverified",
        ),
    )
    insert_only(op, "usage_records")
    insert_columns(
        op,
        "usage_records",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "agent_id",
            "agent_run_id",
            "prompt_id",
            "prompt_version",
            "model",
            "tier",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "outcome",
            "inputs_hash",
        ),
    )
    # Agent runs only move forward, and what they recorded stays (like sync runs).
    op.execute(
        """
        CREATE FUNCTION agent_runs_forward_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'running' THEN
                RAISE EXCEPTION 'agent run % is finished', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF (OLD.context_hash IS NOT NULL
                AND NEW.context_hash IS DISTINCT FROM OLD.context_hash)
               OR (OLD.output IS NOT NULL AND NEW.output IS DISTINCT FROM OLD.output) THEN
                RAISE EXCEPTION 'agent run % results are write-once', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER agent_runs_forward_only BEFORE UPDATE ON agent_runs "
        "FOR EACH ROW EXECUTE FUNCTION agent_runs_forward_only()"
    )


def downgrade() -> None:
    for table in ("agent_runs", "screening_results", "usage_records"):
        op.execute("ALTER TABLE " + table + " NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM agent_runs) OR EXISTS (SELECT 1 FROM screening_results) "
        "OR EXISTS (SELECT 1 FROM usage_records) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: agent runs, screening results or usage exist'; "
        "END IF; END $$"
    )
    op.execute("DROP TABLE usage_records")
    op.execute("DROP TABLE screening_results")
    op.execute("DROP TABLE agent_runs")
    op.execute("DROP FUNCTION agent_runs_forward_only()")
