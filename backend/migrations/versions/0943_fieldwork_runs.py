"""Fieldwork run rows (A-08-T24; A-08 §3 F2, F5, F8, F9; SPEC-657 AC-9.1 to AC-9.3; AUD-12 d,
AUD-13 b, AUD-26 a; DEC-5403).

`fieldwork_run_rows` (insert-only): one row per run row a person started on AUD-12, AUD-13 or
AUD-26: its kind (`fieldwork_attribute`, `flux_explain`, `tie_out`, `client_questions`,
`confirmation_reconcile`), the agent runs it fanned out to (none for a code row), the initiator
("<initiator> via Agent") and, for a code row, its result. Progress is the runs' own state (C6
v2 events, polled as a fallback); nothing here is edited.

Revision ID: 0943
Revises: 0942
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0943"
down_revision = "0942"
branch_labels = None
depends_on = None

INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "target_kind", "target_id", "kind", "run_ids",
    "items", "initiator_user_id", "code_result", "idempotency_key",
)  # fmt: skip


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE fieldwork_run_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            target_kind text NOT NULL
                CHECK (target_kind IN ('attribute_test', 'analytics_set', 'confirmation')),
            target_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('fieldwork_attribute', 'flux_explain', 'tie_out',
                'client_questions', 'confirmation_reconcile')),
            run_ids uuid[] NOT NULL DEFAULT '{}' CHECK (cardinality(run_ids) <= 500),
            items integer NOT NULL CHECK (items BETWEEN 0 AND 500),
            initiator_user_id uuid NOT NULL,
            code_result jsonb NULL,
            idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 255),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, target_id, kind, idempotency_key),
            -- A code row runs no model; an agent row names its runs.
            CHECK ((kind IN ('tie_out', 'client_questions')) = (code_result IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, initiator_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX fieldwork_run_rows_target ON fieldwork_run_rows "
        "(tenant_id, target_id, created_at DESC)"
    )
    tenant_table(op, "fieldwork_run_rows")
    insert_columns(op, "fieldwork_run_rows", INSERTS)
    insert_only(op, "fieldwork_run_rows")


def downgrade() -> None:
    op.execute("DROP TABLE fieldwork_run_rows")
