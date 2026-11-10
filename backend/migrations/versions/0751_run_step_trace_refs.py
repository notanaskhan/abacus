"""P-09-T08 (S32; TASK-6305; DEC-3005): a step's sample records and source, for the trace.

P-09 §4.2's fallback: P-10's runtime schema (0681) has no `sample_refs` or `source_ref` on
`agent_run_steps`, so this expand-only migration adds both, nullable, with no back-fill. The
harness writes them when a tool step ends (P-10-T25), in the step's own update:

- `sample_refs`: at most five `{record_type, id}` the step read, in the order read. The trace's
  step detail resolves them through each owning module, filtered by `visible()`.
- `source_ref`: the firm connection the records came through (its id) or `accrued` for the
  firm's own records (WB-09 a3's "Through").

Revision ID: 0751
Revises: 0750
"""

from __future__ import annotations

from alembic import op

revision = "0751"
down_revision = "0750"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_run_steps "
        "ADD COLUMN sample_refs jsonb NULL CHECK (sample_refs IS NULL OR ("
        "jsonb_typeof(sample_refs) = 'array' AND jsonb_array_length(sample_refs) <= 5)), "
        "ADD COLUMN source_ref text NULL CHECK (source_ref IS NULL OR source_ref = 'accrued' OR "
        "source_ref ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')"
    )
    op.execute("GRANT UPDATE (sample_refs, source_ref) ON agent_run_steps TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (sample_refs, source_ref) ON agent_run_steps FROM abacus_app")
    op.execute("ALTER TABLE agent_run_steps DROP COLUMN source_ref, DROP COLUMN sample_refs")
