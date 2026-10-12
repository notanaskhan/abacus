"""Inbox match proposals (SPEC-033; TASK-065).

`inbox_match_runs`: one per matcher run on an inbox file, with whether it said no request fits.
`inbox_match_proposals`: its proposals in rank order, each a request item with a confidence, a
rationale and code-verified citations, and whether it is shown (a verified quote and enough
confidence). Both insert-only: the matcher proposes, a person assigns (ADR-005).

Revision ID: 0049
Revises: 0048
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE inbox_match_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            inbox_file_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            prompt_ref text NOT NULL CHECK (prompt_ref ~ '^[a-z][a-z0-9_.]*@v[0-9]+$'),
            none_fit boolean NOT NULL,
            truncated boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT inbox_match_runs_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, engagement_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, inbox_file_id) REFERENCES inbox_files (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE inbox_match_proposals (
            tenant_id uuid NOT NULL,
            match_id uuid NOT NULL,
            rank integer NOT NULL CHECK (rank BETWEEN 1 AND 3),
            request_item_id uuid NOT NULL,
            confidence numeric(4, 3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 300),
            citations jsonb NOT NULL,
            shown boolean NOT NULL,
            PRIMARY KEY (tenant_id, match_id, rank),
            FOREIGN KEY (tenant_id, match_id) REFERENCES inbox_match_runs (tenant_id, id)
        )
        """
    )
    for table in ("inbox_match_runs", "inbox_match_proposals"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "inbox_match_runs",
        (
            "id",  # the run sets it, to link its proposals in the same unit of work
            "tenant_id",
            "engagement_id",
            "inbox_file_id",
            "agent_run_id",
            "prompt_ref",
            "none_fit",
            "truncated",
        ),
    )
    insert_columns(
        op,
        "inbox_match_proposals",
        (
            "tenant_id",
            "match_id",
            "rank",
            "request_item_id",
            "confidence",
            "rationale",
            "citations",
            "shown",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE inbox_match_proposals")
    op.execute("DROP TABLE inbox_match_runs")
