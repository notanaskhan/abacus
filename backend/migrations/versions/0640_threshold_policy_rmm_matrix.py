"""A-04 M3 `threshold_policy_rmm_matrix` (A-04-T13; A-04 §4.2 M3; DEC-1951): expand-only.

K-02's `threshold_policies.kind` admits `rmm_matrix`: the firm's risk of material misstatement
for each inherent and control risk (`{rows: [{inherent_risk, control_risk, rmm}]}`), loaded
through the standards import like every other policy. Widening a CHECK is additive.

Revision ID: 0640
Revises: 0614
"""

from __future__ import annotations

from alembic import op

revision = "0640"
down_revision = "0614"
branch_labels = None
depends_on = None

_KINDS_BEFORE = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence', "
    "'attribute_sample_sizes')"
)
_KINDS_AFTER = (
    "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence', "
    "'attribute_sample_sizes', 'rmm_matrix')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE threshold_policies DROP CONSTRAINT threshold_policies_kind_check")
    op.execute(
        "ALTER TABLE threshold_policies ADD CONSTRAINT threshold_policies_kind_check "
        f"CHECK (kind IN {_KINDS_AFTER})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE threshold_policies DROP CONSTRAINT threshold_policies_kind_check")
    op.execute(
        "ALTER TABLE threshold_policies ADD CONSTRAINT threshold_policies_kind_check "
        f"CHECK (kind IN {_KINDS_BEFORE})"
    )
