"""The entry assessor's records (SPEC-037 Q4; TASK-085).

`entry_assessments` (insert-only): one per assessor run on a selected entry: the model's verdict,
the verdict shown (an `explained` whose citations don't all verify is shown as `unclear`), the
rationale, the citations with code's verification, and the prompt. A proposal only: people record
every result (ADR-005).

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_VERDICTS = "('explained', 'not_explained', 'unclear')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE entry_assessments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            selected_item_id uuid NOT NULL,
            agent_run_id uuid NOT NULL,
            prompt_ref text NOT NULL CHECK (prompt_ref ~ '^[a-z][a-z0-9_.]*@v[0-9]+$'),
            verdict text NOT NULL CHECK (verdict IN {_VERDICTS}),
            shown_verdict text NOT NULL CHECK (shown_verdict IN {_VERDICTS}),
            rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 400),
            citations jsonb NOT NULL DEFAULT '[]',
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT entry_assessments_once_per_run UNIQUE (tenant_id, agent_run_id),
            FOREIGN KEY (tenant_id, engagement_id, agent_run_id)
                REFERENCES agent_runs (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX entry_assessments_newest ON entry_assessments "
        "(tenant_id, selected_item_id, created_at DESC)"
    )
    tenant_table(op, "entry_assessments")
    op.execute("REVOKE UPDATE, DELETE ON entry_assessments FROM abacus_app")
    insert_columns(
        op,
        "entry_assessments",
        (
            "tenant_id",
            "engagement_id",
            "selected_item_id",
            "agent_run_id",
            "prompt_ref",
            "verdict",
            "shown_verdict",
            "rationale",
            "citations",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE entry_assessments")
