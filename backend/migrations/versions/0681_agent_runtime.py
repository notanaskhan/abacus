"""P-10 M2: the agent runtime's tables (P-10-T03; P-10 §4.2; ADR-169, ADR-233; SPEC-647).

Steps, plans, questions, events, artifacts, sign-offs, feedback and per-engagement AI settings, in
`agents`. `usage_records` gains the step, session, definition and service line (nullable; the live
`call()` path never sets them, so it stays byte-identical).

Insert-only by trigger: `agent_plans` (a decision is a new version, never an update), `run_events`,
`run_sign_offs`. Human-only, bound to the transaction's actor (the 0023 pattern): a plan decision
and a run sign-off. `run_events` is pruned at 30 days only through `prune_run_events()`, by the
system actor; the durable tables keep the trace.

Revision ID: 0681
Revises: 0680
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0681"
down_revision = "0680"
branch_labels = None
depends_on = None

_RUN_FK = "FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id)"
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_BOUND = (
    "actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true)"
)
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_TABLES = (
    "engagement_ai_settings",
    "agent_feedback",
    "run_sign_offs",
    "run_artifacts",
    "run_events",
    "agent_questions",
    "agent_run_steps",
    "agent_plans",
)
_IMMUTABLE = ("agent_plans", "run_events", "run_sign_offs")
INSERTS: dict[str, tuple[str, ...]] = {
    "agent_plans": (
        "id", "tenant_id", "run_id", "version", "steps", "sources", "state", "decided_by",
        "decided_at", "standing_schedule_id",
    ),
    "agent_run_steps": (
        "id", "tenant_id", "run_id", "seq", "plan_step_key", "level", "kind", "tool_name",
        "args_summary", "args_hash", "state", "needs", "retry_of_step_id",
        "auto_started_by_trigger_id",
    ),
    "agent_questions": (
        "id", "tenant_id", "run_id", "step_id", "steps", "recommended", "other_allowed",
    ),
    "run_events": (
        "tenant_id", "run_id", "session_id", "run_seq", "session_seq", "type", "payload",
    ),
    "run_artifacts": (
        "id", "tenant_id", "run_id", "kind", "name", "size_bytes", "storage_key", "cites",
    ),
    "run_sign_offs": (
        "id", "tenant_id", "run_id", "signed_by", "open_issues_ack", "decisions_ack",
    ),
    "agent_feedback": (
        "id", "tenant_id", "target_kind", "target_id", "rating", "reason_code", "created_by",
    ),
    "engagement_ai_settings": (
        "tenant_id", "engagement_id", "auto_mode", "auto_mode_set_by", "auto_mode_set_at",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "agent_run_steps": (
        "state", "needs", "started_at", "ended_at", "active_ms", "records_read",
        "outputs_summary", "error_code", "error_detail_safe", "usage_record_ids",
    ),
    "agent_questions": ("state", "answer", "answered_by", "answered_at", "skip_default_applied"),
    "run_artifacts": ("version", "state", "saved_to"),
    "engagement_ai_settings": ("auto_mode", "auto_mode_set_by", "auto_mode_set_at"),
}  # fmt: skip
_USAGE = ("step_id", "session_id", "definition_id", "service_line")


def _immutable() -> None:
    op.execute(
        """
        CREATE FUNCTION agent_runtime_rows_immutable() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION agent_runtime_rows_immutable() FROM PUBLIC")
    for table in ("agent_plans", "run_sign_offs"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION agent_runtime_rows_immutable()"
        )
    # The 30-day prune is the one delete: only `prune_run_events()` sets this.
    op.execute(
        """
        CREATE FUNCTION run_events_guard() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('app.run_events_prune', true) = 'on'
               AND OLD.created_at < clock_timestamp() - interval '30 days' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'run_events is insert-only' USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION run_events_guard() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER run_events_immutable BEFORE UPDATE OR DELETE ON run_events "
        "FOR EACH ROW EXECUTE FUNCTION run_events_guard()"
    )
    op.execute(
        """
        CREATE FUNCTION prune_run_events(p_batch integer) RETURNS integer
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            gone integer;
        BEGIN
            IF v_tenant IS NULL
               OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
               OR current_setting('app.actor_id', true)
                  IS DISTINCT FROM 'agents.run_events_prune' THEN
                RAISE EXCEPTION 'only the run events prune deletes run events'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            PERFORM set_config('app.run_events_prune', 'on', true);
            DELETE FROM public.run_events WHERE tenant_id = v_tenant AND id IN (
                SELECT id FROM public.run_events
                 WHERE tenant_id = v_tenant
                   AND created_at < clock_timestamp() - interval '30 days'
                 LIMIT p_batch
            );
            GET DIAGNOSTICS gone = ROW_COUNT;
            PERFORM set_config('app.run_events_prune', 'off', true);
            RETURN gone;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION prune_run_events(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION prune_run_events(integer) TO abacus_app")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE agent_plans (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            steps jsonb NOT NULL,
            sources jsonb NOT NULL DEFAULT '[]',
            state text NOT NULL
                CHECK (state IN ('proposed', 'approved', 'edited', 'cancelled', 'standing')),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            standing_schedule_id uuid NULL,
            {_ACTOR},
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, run_id, version),
            {_RUN_FK},
            FOREIGN KEY (tenant_id, decided_by) REFERENCES memberships (tenant_id, user_id),
            CONSTRAINT agent_plans_decided
                CHECK ((state = 'proposed') = (decided_at IS NULL)
                       OR (state = 'standing' AND decided_at IS NOT NULL)),
            CONSTRAINT agent_plans_decision_is_human CHECK (
                state = 'proposed' OR (
                    decided_by IS NOT NULL AND actor_kind = 'human' AND {_BOUND}
                    AND actor_id = decided_by::text
                )
            )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE agent_run_steps (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq >= 1),
            plan_step_key text NULL CHECK (length(plan_step_key) <= 80),
            level integer NOT NULL DEFAULT 0 CHECK (level >= 0),
            kind text NOT NULL CHECK (kind IN ('tool', 'compute', 'model', 'question', 'decision',
                                               'approval', 'narration', 'wait', 'child_run')),
            tool_name text NULL CHECK (tool_name ~ '^[a-z][a-z_]*\\.[a-z][a-z_]*$'),
            args_summary jsonb NULL,
            args_hash text NULL CHECK (args_hash ~ '^[0-9a-f]{{64}}$'),
            state text NOT NULL DEFAULT 'queued'
                CHECK (state IN ('queued', 'dispatched', 'running', 'waiting_on_inputs', 'blocked',
                                 'succeeded', 'failed', 'cancelled', 'skipped')),
            needs jsonb NULL,
            started_at timestamptz NULL,
            ended_at timestamptz NULL,
            active_ms bigint NOT NULL DEFAULT 0 CHECK (active_ms >= 0),
            records_read integer NOT NULL DEFAULT 0 CHECK (records_read >= 0),
            outputs_summary jsonb NULL,
            error_code text NULL CHECK (error_code ~ '^[a-z][a-z_]{{0,49}}$'),
            error_detail_safe text NULL CHECK (length(error_detail_safe) <= 500),
            retry_of_step_id uuid NULL,
            auto_started_by_trigger_id uuid NULL,
            usage_record_ids uuid[] NOT NULL DEFAULT '{{}}',
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, run_id, seq),
            {_RUN_FK},
            FOREIGN KEY (tenant_id, retry_of_step_id) REFERENCES agent_run_steps (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE agent_questions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            step_id uuid NULL,
            steps jsonb NOT NULL,
            recommended text NULL CHECK (length(recommended) <= 80),
            other_allowed boolean NOT NULL DEFAULT false,
            state text NOT NULL DEFAULT 'open'
                CHECK (state IN ('open', 'answered', 'skipped', 'expired')),
            answer jsonb NULL,
            answered_by uuid NULL,
            answered_at timestamptz NULL,
            skip_default_applied boolean NOT NULL DEFAULT false,
            {_CREATED},
            UNIQUE (tenant_id, id),
            {_RUN_FK},
            FOREIGN KEY (tenant_id, step_id) REFERENCES agent_run_steps (tenant_id, id),
            FOREIGN KEY (tenant_id, answered_by) REFERENCES memberships (tenant_id, user_id),
            CONSTRAINT agent_questions_answered
                CHECK ((state IN ('answered', 'skipped')) = (answered_at IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX agent_questions_one_open ON agent_questions (tenant_id, run_id) "
        "WHERE state = 'open'"
    )
    op.execute(
        f"""
        CREATE TABLE run_events (
            id bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            run_id uuid NULL,
            session_id uuid NULL,
            run_seq bigint NULL CHECK (run_seq >= 1),
            session_seq bigint NULL CHECK (session_seq >= 1),
            type text NOT NULL CHECK (type ~ '^[a-z][a-z_]*\\.?[a-z_]*$'),
            payload jsonb NOT NULL DEFAULT '{{}}',
            {_CREATED},
            PRIMARY KEY (tenant_id, id),
            {_RUN_FK},
            CONSTRAINT run_events_has_stream CHECK (run_id IS NOT NULL OR session_id IS NOT NULL),
            CONSTRAINT run_events_size CHECK (pg_column_size(payload) <= 65536)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX run_events_run_seq ON run_events (tenant_id, run_id, run_seq) "
        "WHERE run_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX run_events_session_seq ON run_events "
        "(tenant_id, session_id, session_seq) WHERE session_id IS NOT NULL"
    )
    op.execute("CREATE INDEX run_events_created_brin ON run_events USING brin (created_at)")
    op.execute(
        f"""
        CREATE TABLE run_artifacts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('xlsx', 'docx', 'pdf', 'csv')),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
            storage_key text NOT NULL CHECK (storage_key LIKE 'tenants/%'),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'saved', 'discarded')),
            saved_to jsonb NULL,
            cites jsonb NOT NULL DEFAULT '[]',
            {_CREATED},
            UNIQUE (tenant_id, id),
            {_RUN_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE run_sign_offs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            signed_by uuid NOT NULL,
            signed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            open_issues_ack jsonb NOT NULL DEFAULT '[]',
            decisions_ack jsonb NOT NULL DEFAULT '[]',
            {_ACTOR},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, run_id),
            {_RUN_FK},
            FOREIGN KEY (tenant_id, signed_by) REFERENCES memberships (tenant_id, user_id),
            CONSTRAINT run_sign_offs_human CHECK (
                actor_kind = 'human' AND {_BOUND} AND actor_id = signed_by::text
            )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE agent_feedback (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            target_kind text NOT NULL
                CHECK (target_kind IN ('step', 'session_item', 'screening_result', 'suggestion')),
            target_id uuid NOT NULL,
            rating text NOT NULL CHECK (rating IN ('up', 'down')),
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z_]{{0,49}}$'),
            created_by uuid NOT NULL,
            {_CREATED},
            UNIQUE (tenant_id, target_kind, target_id, created_by),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engagement_ai_settings (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            auto_mode boolean NOT NULL DEFAULT false,
            auto_mode_set_by uuid NULL,
            auto_mode_set_at timestamptz NULL,
            PRIMARY KEY (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, auto_mode_set_by) REFERENCES memberships (tenant_id, user_id),
            CONSTRAINT engagement_ai_settings_set
                CHECK ((auto_mode_set_by IS NULL) = (auto_mode_set_at IS NULL))
        )
        """
    )
    for table, columns in INSERTS.items():
        tenant_table(op, table)
        insert_columns(op, table, columns)
    # Updates are column grants only (schema_check): drop the default table-wide UPDATE first.
    for table in INSERTS:
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
    for table, columns in UPDATES.items():
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    for table in _IMMUTABLE:
        insert_only(op, table)
    insert_only(op, "agent_feedback")  # registry INSERT_ONLY: feedback is never rewritten
    _immutable()
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_plan FOREIGN KEY (tenant_id, plan_id) "
        "REFERENCES agent_plans (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE usage_records "
        "ADD COLUMN step_id uuid NULL, ADD COLUMN session_id uuid NULL, "
        "ADD COLUMN definition_id uuid NULL, ADD COLUMN service_line text NULL "
        "CHECK (length(service_line) <= 40)"
    )
    op.execute(f"GRANT INSERT ({', '.join(_USAGE)}) ON usage_records TO abacus_app")
    op.execute(
        "CREATE INDEX usage_records_step ON usage_records (tenant_id, step_id) "
        "WHERE step_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX usage_records_step")
    op.execute(f"REVOKE INSERT ({', '.join(_USAGE)}) ON usage_records FROM abacus_app")
    op.execute(
        "ALTER TABLE usage_records " + ", ".join(f"DROP COLUMN {c}" for c in reversed(_USAGE))
    )
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_plan")
    op.execute("DROP FUNCTION prune_run_events(integer)")
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION run_events_guard()")
    op.execute("DROP FUNCTION agent_runtime_rows_immutable()")
