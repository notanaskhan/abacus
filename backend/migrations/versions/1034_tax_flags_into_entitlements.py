"""T-06-T69 (TASK-9018; DEC-6024): the autumn tax flag hygiene. Seven tax rollout flags retire into
the firm's modules (ADR P-28, DEC-55), as A-06's did in 0713:

- T-04's `tax.review_workspace` and `tax.individual_workpapers` and T-07's
  `tax.fiduciary_workpapers`, `tax.fiduciary_k1_release` and `tax.estate_workpapers` into
  `tax_returns`;
- T-05's `tax.entity_workspace` and `tax.workbook_run` into `tax_entity_returns`.

A firm with any of those flags on keeps its access through a row written here; every gate now
reads the entitlement, so a firm without it still gets 404. Expand only: the flag-state rows stay
as history, and no module CHECK changes (both modules exist since 0671 and 0801).

Revision ID: 1034
Revises: 1033
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1034"
down_revision = "1033"
branch_labels = None
depends_on = None

RETIRED = {
    "tax_returns": (
        "tax.review_workspace", "tax.individual_workpapers", "tax.fiduciary_workpapers",
        "tax.fiduciary_k1_release", "tax.estate_workpapers",
    ),
    "tax_entity_returns": ("tax.entity_workspace", "tax.workbook_run"),
}  # fmt: skip


_GRANT = sa.text(
    "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
    "SELECT DISTINCT tenant_id, :module, DATE '2000-01-01', 'T-06-T69' "
    "FROM feature_flag_states WHERE flag = ANY(:flags) AND value = 'true' "
    "ON CONFLICT DO NOTHING"
)


def upgrade() -> None:
    for module, flags in RETIRED.items():
        op.execute(_GRANT.bindparams(module=module, flags=list(flags)))


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE set_by = 'T-06-T69'")
