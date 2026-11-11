"""A finished run's event sequence and write counters may move (S36 end pass; P-10-T38;
TASK-6825; DEC-3417).

`agent_runs_forward_only` (0680, 0711) refuses any write to a finished row that keeps its state.
P-10-T38's approved writes land after the run ended: a person approves the Save to Files proposal
once the run has succeeded, then `files.save_approved` appends the run's "saved" item
(`event_seq`) and moves `writes_waiting` to `writes_done`. The guard now lets exactly those three
columns change on a finished row whose state stays. Every other column stays frozen, and results
stay write-once.

The downgrade restores 0711's definition.

Revision ID: 0813
Revises: 0812
"""

from __future__ import annotations

from alembic import op

revision = "0813"
down_revision = "0812"
branch_labels = None
depends_on = None

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
            -- S36 end pass (P-10-T38, DEC-3417): a finished run's approved writes land after it
            -- ended (a person approves after the run succeeded), so its event sequence and its
            -- write counters may still move; nothing else on a finished row changes.
            IF OLD.status <> 'running' AND NEW.state IS NOT DISTINCT FROM OLD.state
               AND (to_jsonb(NEW) - ARRAY['event_seq', 'writes_done', 'writes_waiting'])
                   = (to_jsonb(OLD) - ARRAY['event_seq', 'writes_done', 'writes_waiting'])
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
_FORWARD_ONLY_0711 = """
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


def upgrade() -> None:
    op.execute(_FORWARD_ONLY)


def downgrade() -> None:
    op.execute(_FORWARD_ONLY_0711)
