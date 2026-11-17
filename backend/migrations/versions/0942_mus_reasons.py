"""Monetary-unit sampling's selection reasons (A-08-T13; A-08 §6 constraint swaps; ADR P-57;
DEC-5402).

`sample_items.selection_reason` gains `certainty` (an item at or above the sampling interval) and
`pps` (a systematic probability-proportional-to-size hit). The method `monetary_unit` and the
firm content kind `mus_confidence_factors` arrived with 0895.

Revision ID: 0942
Revises: 0941
"""

from __future__ import annotations

from alembic import op

revision = "0942"
down_revision = "0941"
branch_labels = None
depends_on = None

_BEFORE = "('random', 'threshold', 'risk_score', 'unpredictable', 'named')"
_AFTER = "('random', 'threshold', 'risk_score', 'unpredictable', 'named', 'certainty', 'pps')"


def _reasons(values: str) -> None:
    op.execute("ALTER TABLE sample_items DROP CONSTRAINT sample_items_selection_reason_check")
    op.execute(
        "ALTER TABLE sample_items ADD CONSTRAINT sample_items_selection_reason_check "
        f"CHECK (selection_reason IN {values})"
    )


def upgrade() -> None:
    _reasons(_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM sample_items WHERE selection_reason IN ('certainty', 'pps')")
    _reasons(_BEFORE)
