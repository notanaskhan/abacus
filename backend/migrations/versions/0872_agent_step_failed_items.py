"""W-02-T19 (S43; TASK-7935; W-02 §4.2; DEC-4930): a step's per-item failure ledger and the scope
of a retry, expand-only.

- `failed_items`: the references a step could not read, `[{ref_type, ref_id, source, error_code}]`
  (identifiers and codes only, never content). `[]` for a step that read everything. The run's
  "Prepared with 1 gap" and "238 of 241" are counted from it by code.
- `retry_scope`: on a retry row, what it re-ran: `all` (the step again) or `failed_items` (only
  the references the retried row's ledger names). NULL on a first attempt.

RLS unchanged. The app role inserts `retry_scope` with a retry row and sets `failed_items` when the
step ends (the row is written `running`, then finished in its own update).

Revision ID: 0872
Revises: 0871
"""

from __future__ import annotations

from alembic import op

revision = "0872"
down_revision = "0871"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_run_steps "
        "ADD COLUMN failed_items jsonb NOT NULL DEFAULT '[]'::jsonb CHECK ("
        "jsonb_typeof(failed_items) = 'array' AND jsonb_array_length(failed_items) <= 1000), "
        "ADD COLUMN retry_scope text NULL CHECK (retry_scope IN ('all', 'failed_items'))"
    )
    op.execute("GRANT INSERT (retry_scope) ON agent_run_steps TO abacus_app")
    op.execute("GRANT UPDATE (failed_items) ON agent_run_steps TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (failed_items) ON agent_run_steps FROM abacus_app")
    op.execute("REVOKE INSERT (retry_scope) ON agent_run_steps FROM abacus_app")
    op.execute("ALTER TABLE agent_run_steps DROP COLUMN retry_scope, DROP COLUMN failed_items")
