"""P-10 M1: agent runs v2 (P-10-T02; P-10 §4.2; ADR-169, ADR-233; SPEC-647; expand-only).

`agent_runs` gains the canonical `state` and all a run v2 reads. `status` and its CHECK stay,
so the live specialists keep writing `status` until the contract phase after the window:

- A sync trigger maps both ways. A legacy write of `status` sets `state` (`completed` to
  `succeeded`, `escalated` to `needs_input` with reason `escalated`). A v2 write of `state` sets
  `status` (active states to `running`; `succeeded`, `approved`, `partially_approved`, `rejected`
  to `completed`; `failed`, `cancelled` to `failed`), and the columns `status` constrains
  (`finished_at`, `failure_code`, `queued_reason`).
- The same trigger refuses an illegal transition: forward only, `failed` and `cancelled` reachable
  from any active state, and the review outcomes move among themselves, since an Undo changes them.
- Rows from before this migration keep `state` NULL until P-10-T14's backfill.

`tenant_counters` gives `run_number`: `UPDATE … RETURNING` in the unit of work.

Revision ID: 0680
Revises: 0673
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0680"
down_revision = "0673"
branch_labels = None
depends_on = None

_STATES = (
    "queued", "planning", "awaiting_plan_approval", "dispatched", "running", "needs_input",
    "blocked_on_decision", "waiting_on_inputs", "succeeded", "approved", "partially_approved",
    "rejected", "failed", "cancelled",
)  # fmt: skip
_TRIGGER_KINDS = (
    "manual", "schedule", "agent_trigger", "engagement_trigger", "retry", "test",
    "engagement_plan", "agent_column", "event_policy",
)  # fmt: skip
_COLUMNS = (
    "state", "state_reason", "blocked_on", "run_number", "session_id", "definition_id",
    "definition_version", "mode", "trigger_kind", "trigger_ref", "parent_run_id", "work_item_ref",
    "subject_ref", "inputs", "auto_mode", "runs_as_user_id", "test", "plan_id", "client_scope",
    "records_read", "citations_count", "writes_done", "writes_waiting", "agent_ms",
    "agent_minutes", "cost_usd", "region", "route", "terms_version", "signed_off_by",
    "signed_off_at", "event_seq",
)  # fmt: skip
_INSERTS = (
    "state", "state_reason", "blocked_on", "run_number", "session_id", "definition_id",
    "definition_version", "mode", "trigger_kind", "trigger_ref", "parent_run_id", "work_item_ref",
    "subject_ref", "inputs", "auto_mode", "runs_as_user_id", "test", "client_scope", "region",
    "route", "terms_version",
)  # fmt: skip
_UPDATES = (
    "state", "state_reason", "blocked_on", "session_id", "plan_id", "client_scope",
    "records_read", "citations_count", "writes_done", "writes_waiting", "agent_ms",
    "agent_minutes", "cost_usd", "region", "route", "terms_version", "signed_off_by",
    "signed_off_at", "event_seq",
)  # fmt: skip


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


_SYNC = """
    CREATE FUNCTION agent_runs_state_sync() RETURNS trigger
        LANGUAGE plpgsql
    AS $$
    DECLARE
        state_written boolean := false;
        allowed text[];
    BEGIN
        IF TG_OP = 'INSERT' THEN
            state_written := NEW.state IS NOT NULL;
        ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
            state_written := true;
        END IF;

        IF state_written THEN
            NEW.status := CASE
                WHEN NEW.state IN ('succeeded', 'approved', 'partially_approved', 'rejected')
                    THEN 'completed'
                WHEN NEW.state IN ('failed', 'cancelled') THEN 'failed'
                ELSE 'running'
            END;
            IF NEW.status = 'running' THEN
                NEW.finished_at := NULL;
                NEW.failure_code := NULL;
            ELSE
                NEW.finished_at := COALESCE(NEW.finished_at, clock_timestamp());
                NEW.queued_reason := NULL;
                NEW.estimated_start_at := NULL;
                IF NEW.status = 'failed' THEN
                    NEW.failure_code := COALESCE(
                        NEW.failure_code,
                        CASE WHEN NEW.state = 'cancelled' THEN 'cancelled' ELSE 'run_failed' END
                    );
                ELSE
                    NEW.failure_code := NULL;
                END IF;
            END IF;
        ELSIF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
            NEW.state := CASE NEW.status
                WHEN 'completed' THEN 'succeeded'
                WHEN 'escalated' THEN 'needs_input'
                WHEN 'failed' THEN 'failed'
                ELSE 'running'
            END;
            IF NEW.status = 'escalated' THEN
                NEW.state_reason := 'escalated';
            END IF;
        END IF;

        IF TG_OP = 'UPDATE' AND OLD.state IS NOT NULL
           AND NEW.state IS DISTINCT FROM OLD.state THEN
            allowed := CASE OLD.state
                WHEN 'queued' THEN ARRAY['planning', 'dispatched', 'running']
                WHEN 'planning' THEN ARRAY['awaiting_plan_approval', 'dispatched']
                WHEN 'awaiting_plan_approval' THEN ARRAY['planning', 'dispatched']
                WHEN 'dispatched' THEN ARRAY['running']
                WHEN 'running' THEN ARRAY['needs_input', 'blocked_on_decision',
                                          'waiting_on_inputs', 'succeeded']
                WHEN 'needs_input' THEN ARRAY['running', 'succeeded']
                WHEN 'blocked_on_decision' THEN ARRAY['running']
                WHEN 'waiting_on_inputs' THEN ARRAY['running']
                WHEN 'succeeded' THEN ARRAY['approved', 'partially_approved', 'rejected']
                WHEN 'approved' THEN ARRAY['succeeded', 'partially_approved', 'rejected']
                WHEN 'partially_approved' THEN ARRAY['succeeded', 'approved', 'rejected']
                WHEN 'rejected' THEN ARRAY['succeeded', 'approved', 'partially_approved']
                ELSE ARRAY[]::text[]
            END;
            IF OLD.state NOT IN ('succeeded', 'approved', 'partially_approved', 'rejected',
                                 'failed', 'cancelled') THEN
                allowed := allowed || ARRAY['failed', 'cancelled'];
            END IF;
            IF NOT NEW.state = ANY(allowed) THEN
                RAISE EXCEPTION 'agent run state % cannot move to %', OLD.state, NEW.state
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE agent_runs
            ADD COLUMN state text NULL CHECK (state IN ({_in(_STATES)})),
            ADD COLUMN state_reason text NULL CHECK (state_reason ~ '^[a-z][a-z_]{{0,49}}$'),
            ADD COLUMN blocked_on jsonb NULL,
            ADD COLUMN run_number bigint NULL CHECK (run_number > 0),
            ADD COLUMN session_id uuid NULL,
            ADD COLUMN definition_id uuid NULL,
            ADD COLUMN definition_version integer NULL CHECK (definition_version >= 1),
            ADD COLUMN mode text NULL CHECK (mode IN ('plan', 'run', 'auto')),
            ADD COLUMN trigger_kind text NULL CHECK (trigger_kind IN ({_in(_TRIGGER_KINDS)})),
            ADD COLUMN trigger_ref text NULL CHECK (length(trigger_ref) <= 200),
            ADD COLUMN parent_run_id uuid NULL,
            ADD COLUMN work_item_ref text NULL CHECK (length(work_item_ref) <= 200),
            ADD COLUMN subject_ref text NULL CHECK (length(subject_ref) <= 200),
            ADD COLUMN inputs jsonb NULL,
            ADD COLUMN auto_mode boolean NOT NULL DEFAULT false,
            ADD COLUMN runs_as_user_id uuid NULL,
            ADD COLUMN test boolean NOT NULL DEFAULT false,
            ADD COLUMN plan_id uuid NULL,
            ADD COLUMN client_scope uuid[] NOT NULL DEFAULT '{{}}',
            ADD COLUMN records_read integer NOT NULL DEFAULT 0 CHECK (records_read >= 0),
            ADD COLUMN citations_count integer NOT NULL DEFAULT 0 CHECK (citations_count >= 0),
            ADD COLUMN writes_done integer NOT NULL DEFAULT 0 CHECK (writes_done >= 0),
            ADD COLUMN writes_waiting integer NOT NULL DEFAULT 0 CHECK (writes_waiting >= 0),
            ADD COLUMN agent_ms bigint NOT NULL DEFAULT 0 CHECK (agent_ms >= 0),
            ADD COLUMN agent_minutes integer NOT NULL DEFAULT 0 CHECK (agent_minutes >= 0),
            ADD COLUMN cost_usd numeric(12, 4) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
            ADD COLUMN region text NULL CHECK (length(region) <= 40),
            ADD COLUMN route text NULL CHECK (route IN ('direct', 'bedrock', 'fake')),
            ADD COLUMN terms_version text NULL CHECK (length(terms_version) <= 40),
            ADD COLUMN signed_off_by uuid NULL,
            ADD COLUMN signed_off_at timestamptz NULL,
            ADD COLUMN event_seq bigint NOT NULL DEFAULT 0 CHECK (event_seq >= 0),
            ADD CONSTRAINT agent_runs_parent FOREIGN KEY (tenant_id, parent_run_id)
                REFERENCES agent_runs (tenant_id, id),
            ADD CONSTRAINT agent_runs_runs_as FOREIGN KEY (tenant_id, runs_as_user_id)
                REFERENCES memberships (tenant_id, user_id),
            ADD CONSTRAINT agent_runs_signed_off_by FOREIGN KEY (tenant_id, signed_off_by)
                REFERENCES memberships (tenant_id, user_id),
            ADD CONSTRAINT agent_runs_signed_off_both
                CHECK ((signed_off_by IS NULL) = (signed_off_at IS NULL))
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX agent_runs_run_number ON agent_runs (tenant_id, run_number) "
        "WHERE run_number IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX agent_runs_session ON agent_runs (tenant_id, session_id) "
        "WHERE session_id IS NOT NULL"
    )
    op.execute(_SYNC)
    op.execute("REVOKE ALL ON FUNCTION agent_runs_state_sync() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER agent_runs_state_sync BEFORE INSERT OR UPDATE ON agent_runs "
        "FOR EACH ROW EXECUTE FUNCTION agent_runs_state_sync()"
    )
    op.execute(f"GRANT INSERT ({', '.join(_INSERTS)}) ON agent_runs TO abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_UPDATES)}) ON agent_runs TO abacus_app")

    op.execute(
        """
        CREATE TABLE tenant_counters (
            tenant_id uuid NOT NULL,
            name text NOT NULL CHECK (name ~ '^[a-z][a-z_]{0,49}$'),
            value bigint NOT NULL DEFAULT 0 CHECK (value >= 0),
            PRIMARY KEY (tenant_id, name)
        )
        """
    )
    tenant_table(op, "tenant_counters")
    insert_columns(op, "tenant_counters", ("tenant_id", "name", "value"))
    op.execute("GRANT UPDATE (value) ON tenant_counters TO abacus_app")
    op.execute("REVOKE DELETE ON tenant_counters FROM abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE tenant_counters")
    op.execute("DROP TRIGGER agent_runs_state_sync ON agent_runs")
    op.execute("DROP FUNCTION agent_runs_state_sync()")
    op.execute(f"REVOKE UPDATE ({', '.join(_UPDATES)}) ON agent_runs FROM abacus_app")
    op.execute(f"REVOKE INSERT ({', '.join(_INSERTS)}) ON agent_runs FROM abacus_app")
    op.execute("DROP INDEX agent_runs_session")
    op.execute("DROP INDEX agent_runs_run_number")
    op.execute(
        "ALTER TABLE agent_runs "
        "DROP CONSTRAINT agent_runs_signed_off_both, DROP CONSTRAINT agent_runs_signed_off_by, "
        "DROP CONSTRAINT agent_runs_runs_as, DROP CONSTRAINT agent_runs_parent, "
        + ", ".join(f"DROP COLUMN {c}" for c in reversed(_COLUMNS))
    )
