"""The runs an issue started, the proposals its fix produced, and its explanations (T-04-T31;
TASK-6819; DEC-3413; P-04 SHL-15 a', a'', d; T-04 AC-4.3 to AC-4.5).

Three insert-only tables in `review`, so an issue can name what its fix run proposed and the
approval of that proposal can resolve the issue as the person who approved it, and so Explain's
text is stored with only the citations that verified:

- `issue_runs`: the run a person's action started for the issue (`fix`: Set Fix Instructions;
  `explain`: Explain…). Written in the person's transaction (`actor_kind = 'human'`).
- `issue_fix_proposals`: the proposal a fix run created, one per run. Written by the agent
  (`actor_kind = 'agent'`, its `actor_id` the run); `proposal_id` is unique, so one proposal
  resolves at most one issue.
- `issue_explanations`: the explanation text (sealed), the verified citation ids it shows, its
  run. Written by the agent; never a decision.

Each carries the transaction's actor (0094's rule), is forced RLS, has no UPDATE, DELETE or
TRUNCATE for the app and a `review_rows_immutable` trigger. Expand-only; the downgrade drops them.

Revision ID: 0812
Revises: 0811
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0812"
down_revision = "0811"
branch_labels = None
depends_on = None

_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_TRANSACTION_ACTOR = (
    "CHECK (actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_TABLES = ("issue_runs", "issue_fix_proposals", "issue_explanations")
INSERTS: dict[str, tuple[str, ...]] = {
    "issue_runs": ("tenant_id", "issue_id", "agent_run_id", "purpose"),
    "issue_fix_proposals": ("tenant_id", "issue_id", "agent_run_id", "proposal_id"),
    "issue_explanations": (
        "tenant_id", "issue_id", "agent_run_id", "text_sealed", "citation_ids",
    ),
}  # fmt: skip


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE issue_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ('fix', 'explain')),
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, agent_run_id),
            CONSTRAINT issue_runs_by_a_person CHECK (actor_kind = 'human'),
            CONSTRAINT issue_runs_actor_is_transaction_actor {_TRANSACTION_ACTOR},
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX issue_runs_by_issue ON issue_runs (tenant_id, issue_id, created_at)")
    op.execute(
        f"""
        CREATE TABLE issue_fix_proposals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            proposal_id uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, proposal_id),
            UNIQUE (tenant_id, agent_run_id),
            CONSTRAINT issue_fix_proposals_by_the_agent CHECK (actor_kind = 'agent'),
            CONSTRAINT issue_fix_proposals_actor_is_transaction_actor {_TRANSACTION_ACTOR},
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id),
            FOREIGN KEY (tenant_id, agent_run_id) REFERENCES issue_runs (tenant_id, agent_run_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE issue_explanations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            text_sealed bytea NOT NULL CHECK (octet_length(text_sealed) <= 65536),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(citation_ids) <= 20),
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT issue_explanations_by_the_agent CHECK (actor_kind = 'agent'),
            CONSTRAINT issue_explanations_actor_is_transaction_actor {_TRANSACTION_ACTOR},
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id),
            FOREIGN KEY (tenant_id, agent_run_id) REFERENCES issue_runs (tenant_id, agent_run_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX issue_explanations_by_issue ON issue_explanations "
        "(tenant_id, issue_id, created_at)"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION review_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION review_rows_immutable()"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
