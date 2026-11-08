"""P-10-T14: the legacy agent run backfill may write (P-10 §4.4; SPEC-647; ADR-090).

Rows from before 0680 have `state` NULL. `AgentRunBackfill` gives each its legacy state
(`completed` to `succeeded`, `escalated` to `needs_input` with reason `escalated`, `failed` to
`failed`, `running` to `running`), a `run_number` from `tenant_counters` and, where a session item
names the run, its `session_id`. Two guards stood in the way and are narrowed here, not dropped:

- `agent_runs_forward_only` refused any write to a finished row whose `state` was NULL. It now
  lets through exactly a backfill write: `state` from NULL, and no column changing but `state`,
  `state_reason`, `run_number` and `session_id`.
- `agent_runs_state_sync` mapped a state write onto `status` (and reset `finished_at`). A backfill
  write (state from NULL, status unchanged) now keeps `status` and accepts only the legacy mapping.
- A `run_number`, once set, never changes; the app role may now write it (`UPDATE (run_number)`).

Revision ID: 0711
Revises: 0710
"""

from __future__ import annotations

from alembic import op

revision = "0711"
down_revision = "0710"
branch_labels = None
depends_on = None

_SYNC = """
    CREATE OR REPLACE FUNCTION agent_runs_state_sync() RETURNS trigger
        LANGUAGE plpgsql
    AS $$
    DECLARE
        state_written boolean := false;
        allowed text[];
    BEGIN
        -- P-10-T14: a run number, once set, never changes.
        IF TG_OP = 'UPDATE' AND OLD.run_number IS NOT NULL
           AND NEW.run_number IS DISTINCT FROM OLD.run_number THEN
            RAISE EXCEPTION 'agent run % keeps its run number', OLD.id
                USING ERRCODE = 'check_violation';
        END IF;
        -- P-10-T14: the legacy backfill gives a pre-v2 row its state without touching status.
        -- Only the legacy mapping is accepted; status, finished_at and failure_code stay.
        IF TG_OP = 'UPDATE' AND OLD.state IS NULL AND NEW.state IS NOT NULL
           AND NEW.status IS NOT DISTINCT FROM OLD.status THEN
            IF NEW.state IS DISTINCT FROM (CASE OLD.status
                    WHEN 'completed' THEN 'succeeded'
                    WHEN 'escalated' THEN 'needs_input'
                    WHEN 'failed' THEN 'failed'
                    ELSE 'running' END) THEN
                RAISE EXCEPTION 'agent run % backfills only to its legacy state', OLD.id
                    USING ERRCODE = 'check_violation';
            END IF;
            NEW.state_reason := CASE WHEN OLD.status = 'escalated' THEN 'escalated'
                                     ELSE NEW.state_reason END;
            RETURN NEW;
        END IF;
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
_FORWARD_ONLY = """
        CREATE OR REPLACE FUNCTION agent_runs_forward_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            -- P-10-T14: a pre-v2 row taking its state, run number and session link, nothing
            -- else (the state sync trigger accepts only the legacy mapping).
            IF OLD.state IS NULL AND NEW.state IS NOT NULL
               AND (to_jsonb(NEW) - ARRAY['state', 'state_reason', 'run_number', 'session_id'])
                   = (to_jsonb(OLD) - ARRAY['state', 'state_reason', 'run_number', 'session_id'])
            THEN
                RETURN NEW;
            END IF;
            IF OLD.status <> 'running'
               AND (OLD.state IS NULL OR NEW.state IS NOT DISTINCT FROM OLD.state) THEN
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
        END;
        $$
"""
# 0680's definitions, restored on downgrade.
_SYNC_0680 = """
    CREATE OR REPLACE FUNCTION agent_runs_state_sync() RETURNS trigger
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
_FORWARD_ONLY_0680 = """
        CREATE OR REPLACE FUNCTION agent_runs_forward_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'running'
               AND (OLD.state IS NULL OR NEW.state IS NOT DISTINCT FROM OLD.state) THEN
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
        END;
        $$
"""


def upgrade() -> None:
    op.execute(_SYNC)
    op.execute(_FORWARD_ONLY)
    op.execute("GRANT UPDATE (run_number) ON agent_runs TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (run_number) ON agent_runs FROM abacus_app")
    op.execute(_FORWARD_ONLY_0680)
    op.execute(_SYNC_0680)
