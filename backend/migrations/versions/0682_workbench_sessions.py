"""P-10 M3: Workbench sessions (P-10-T04; P-10 §4.2; ADR-235; SPEC-647).

A session is the thread view of one or more runs. `workbench_sessions` is soft-delete only;
`session_items` is insert-only and schema-versioned, so a soft-deleted session keeps its items and
runs (AC-S5). `client_scope` is computed from every client read. `agent_runs.session_id` gets its
foreign key here, where the table exists.

Revision ID: 0682
Revises: 0681
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0682"
down_revision = "0681"
branch_labels = None
depends_on = None

SESSION_INSERTS = (
    "id", "tenant_id", "title", "owner_user_id", "origin", "definition_id", "context_refs",
    "client_scope",
)  # fmt: skip
SESSION_UPDATES = (
    "title", "state", "context_refs", "client_scope", "last_item_at", "item_seq", "deleted_at",
)  # fmt: skip
ITEM_INSERTS = (
    "id", "tenant_id", "session_id", "seq", "kind", "payload", "run_id", "step_id", "actor_kind",
    "actor_id", "classification",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE workbench_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            owner_user_id uuid NOT NULL,
            origin text NOT NULL CHECK (origin IN ('manual', 'schedule', 'trigger', 'test',
                                                   'saved_prompt', 'engagement_run')),
            definition_id uuid NULL,
            state text NOT NULL DEFAULT 'live'
                CHECK (state IN ('live', 'running', 'awaiting_answer', 'ready_for_review',
                                 'complete', 'failed')),
            context_refs jsonb NOT NULL DEFAULT '[]',
            client_scope uuid[] NOT NULL DEFAULT '{}',
            last_item_at timestamptz NULL,
            item_seq bigint NOT NULL DEFAULT 0 CHECK (item_seq >= 0),
            deleted_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, owner_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX workbench_sessions_owner ON workbench_sessions "
        "(tenant_id, owner_user_id, last_item_at DESC) WHERE deleted_at IS NULL"
    )
    op.execute(
        """
        CREATE TABLE session_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            session_id uuid NOT NULL,
            seq bigint NOT NULL CHECK (seq >= 1),
            kind text NOT NULL CHECK (kind IN ('user_message', 'agent_blocks', 'plan', 'question',
                                               'answer', 'tool_card', 'artifact', 'notice')),
            payload jsonb NOT NULL CHECK (payload ? 'v'),
            run_id uuid NULL,
            step_id uuid NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 100),
            classification text NOT NULL
                CHECK (classification IN ('public', 'internal', 'confidential', 'restricted')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, session_id, seq),
            FOREIGN KEY (tenant_id, session_id) REFERENCES workbench_sessions (tenant_id, id),
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, step_id) REFERENCES agent_run_steps (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION session_items_immutable() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'session_items is insert-only' USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION session_items_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER session_items_immutable BEFORE UPDATE OR DELETE ON session_items "
        "FOR EACH ROW EXECUTE FUNCTION session_items_immutable()"
    )
    op.execute(
        """
        CREATE FUNCTION workbench_sessions_soft_delete() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'a session is soft-deleted, never removed'
                USING ERRCODE = 'check_violation';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION workbench_sessions_soft_delete() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER workbench_sessions_soft_delete BEFORE DELETE ON workbench_sessions "
        "FOR EACH ROW EXECUTE FUNCTION workbench_sessions_soft_delete()"
    )
    tenant_table(op, "workbench_sessions")
    tenant_table(op, "session_items")
    insert_columns(op, "workbench_sessions", SESSION_INSERTS)
    insert_columns(op, "session_items", ITEM_INSERTS)
    insert_only(op, "session_items")
    op.execute("REVOKE DELETE ON workbench_sessions FROM abacus_app")
    op.execute("REVOKE UPDATE ON workbench_sessions FROM abacus_app")  # column grants only
    op.execute(f"GRANT UPDATE ({', '.join(SESSION_UPDATES)}) ON workbench_sessions TO abacus_app")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_session_fk "
        "FOREIGN KEY (tenant_id, session_id) REFERENCES workbench_sessions (tenant_id, id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_session_fk")
    op.execute("DROP TABLE session_items")
    op.execute("DROP TABLE workbench_sessions")
    op.execute("DROP FUNCTION workbench_sessions_soft_delete()")
    op.execute("DROP FUNCTION session_items_immutable()")
