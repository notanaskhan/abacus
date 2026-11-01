"""Joins the two heads main carried after #1035 (TASK-2718): 0582 (a mapping set's prior-year
source, DEC-1769) and 0613-0614 (A-04's planning and procedure tailoring), both on 0612. Neither
touches the other's objects (0582 alters `mapping_sets` only), so the join changes nothing
(DEC-06: the later change reconciles).

Revision ID: 0615
Revises: 0582, 0614
"""

from __future__ import annotations

revision = "0615"
down_revision = ("0582", "0614")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
