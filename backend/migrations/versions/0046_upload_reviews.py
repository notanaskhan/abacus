"""Upload reviews (SPEC-030; TASK-058).

`upload_reviews`: one per upload reviewer run (an evidence version, a prompt version), with
whether it found no concerns and whether it saw only part of the document. `upload_review_flags`:
its flags, each with code-verified citations and whether it is shown to the firm (a verified
quote, confidence at or above the spec's threshold). Both insert-only; agents propose, people
decide (ADR-005).

Revision ID: 0046
Revises: 0045
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE upload_reviews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            prompt_ref text NOT NULL CHECK (prompt_ref ~ '^[a-z][a-z0-9_.]*@v[0-9]+$'),
            document_kind text NULL CHECK (length(document_kind) BETWEEN 1 AND 40),
            no_concerns boolean NOT NULL,
            truncated boolean NOT NULL DEFAULT false,
            created_by_kind text NOT NULL DEFAULT 'agent' CHECK (created_by_kind = 'agent'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT upload_reviews_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, engagement_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, agent_run_id, evidence_version_id)
                REFERENCES agent_runs (tenant_id, id, evidence_version_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE upload_review_flags (
            tenant_id uuid NOT NULL,
            review_id uuid NOT NULL,
            position integer NOT NULL CHECK (position BETWEEN 1 AND 5),
            category text NOT NULL CHECK (category IN ('irrelevant', 'draft', 'altered')),
            confidence numeric(4, 3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 600),
            citations jsonb NOT NULL,
            shown boolean NOT NULL,
            PRIMARY KEY (tenant_id, review_id, position),
            FOREIGN KEY (tenant_id, review_id) REFERENCES upload_reviews (tenant_id, id)
        )
        """
    )
    for table in ("upload_reviews", "upload_review_flags"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "upload_reviews",
        (
            "id",  # the run sets it, to link its flags in the same unit of work
            "tenant_id",
            "engagement_id",
            "evidence_version_id",
            "agent_run_id",
            "prompt_ref",
            "document_kind",
            "no_concerns",
            "truncated",
        ),
    )
    insert_columns(
        op,
        "upload_review_flags",
        (
            "tenant_id",
            "review_id",
            "position",
            "category",
            "confidence",
            "rationale",
            "citations",
            "shown",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE upload_review_flags")
    op.execute("DROP TABLE upload_reviews")
