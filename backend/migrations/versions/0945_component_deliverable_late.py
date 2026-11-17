"""Component deliverables go late once (A-09-T28; A-09 §3.6 Story 6.3; SPEC-658 F6; AUD-35 d;
POR-23 c; DEC-5406).

`component_deliverables.went_late_at`: stamped once, by the sweep at 06:00 firm time on the first
day an Expected deliverable is past its due date, so `component_deliverable.late` is emitted once
per deliverable (a return and a later due date clear it, so a returned deliverable can go late
again). Late itself stays derived on read.

Revision ID: 0945
Revises: 0944
"""

from __future__ import annotations

from alembic import op

revision = "0945"
down_revision = "0944"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE component_deliverables ADD COLUMN went_late_at timestamptz NULL")
    op.execute("GRANT UPDATE (went_late_at) ON component_deliverables TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (went_late_at) ON component_deliverables FROM abacus_app")
    op.execute("ALTER TABLE component_deliverables DROP COLUMN went_late_at")
