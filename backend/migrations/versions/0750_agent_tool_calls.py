"""P-10-T22 (S32; TASK-6301; DEC-3001): the tool call ledger behind C17's idempotency key.

One row per `(run_id, step_seq, attempt)` that ran a `propose` or `approved_write` tool. The first
call claims the key (state `claimed`, with the hash of its arguments) before its effect runs, then
records its answer (identifiers and states only: `validate_tool` refuses free text in a write's
answer) and turns `done`. A retried activity with the same key and arguments gets the stored
answer, and the effect never runs twice (SPEC-647 AC-R7). The same key with other arguments is
refused. Reads and computes have no side effect and are not keyed.

A row only moves `claimed` -> `done`, once (trigger); a claim whose effect failed before it
committed is deleted by the runtime so the retry can claim again. Kept with the durable run records
(7 years or the engagement's retention).

Revision ID: 0750
Revises: 0745
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0750"
down_revision = "0745"
branch_labels = None
depends_on = None

_INSERTS = ("id", "tenant_id", "run_id", "step_seq", "attempt", "tool_name", "args_hash")
_UPDATES = ("state", "result", "completed_at")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_tool_calls (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            run_id uuid NOT NULL,
            step_seq integer NOT NULL CHECK (step_seq >= 1),
            attempt integer NOT NULL CHECK (attempt >= 1),
            tool_name text NOT NULL CHECK (tool_name ~ '^[a-z][a-z_]*\\.[a-z][a-z_]*$'),
            args_hash text NOT NULL CHECK (args_hash ~ '^[0-9a-f]{64}$'),
            state text NOT NULL DEFAULT 'claimed' CHECK (state IN ('claimed', 'done')),
            result jsonb NULL CHECK (result IS NULL OR octet_length(result::text) <= 16384),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            completed_at timestamptz NULL,
            CONSTRAINT agent_tool_calls_done CHECK (
                (state = 'done') = (completed_at IS NOT NULL AND result IS NOT NULL)
            ),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, run_id, step_seq, attempt),
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id)
        )
        """
    )
    tenant_table(op, "agent_tool_calls")
    insert_columns(op, "agent_tool_calls", _INSERTS)
    op.execute("REVOKE UPDATE ON agent_tool_calls FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_UPDATES)}) ON agent_tool_calls TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION agent_tool_calls_guard() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.state = 'claimed' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'a done tool call is kept' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.state <> 'claimed' OR NEW.state <> 'done'
               OR NEW.run_id <> OLD.run_id OR NEW.step_seq <> OLD.step_seq
               OR NEW.attempt <> OLD.attempt OR NEW.args_hash <> OLD.args_hash
               OR NEW.tool_name <> OLD.tool_name THEN
                RAISE EXCEPTION 'a tool call moves claimed to done once'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION agent_tool_calls_guard() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER agent_tool_calls_guard BEFORE UPDATE OR DELETE ON agent_tool_calls "
        "FOR EACH ROW EXECUTE FUNCTION agent_tool_calls_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE agent_tool_calls")
    op.execute("DROP FUNCTION agent_tool_calls_guard()")
