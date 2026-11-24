"""C-02-T39 (S53; TASK-8920; C-02 F8; C12; DEC-5922; amber): a December close's hand-off carries
its own schedules and close items. Expand-only: two add-only CHECK swaps on T-06's C12 children.

- `tb_handoff_schedules.kind` admits `prepaid_expenses`, `deferred_revenue` and
  `shareholder_distributions` (CLS-12's five: the fixed asset register, prepaid insurance,
  deferred revenue, shareholder distributions and accrued payroll, the last on the existing
  `accrued_liabilities`).
- `tb_handoff_tax_items.item_kind` admits `close_issue`: a tax-relevant close note the person
  toggles on becomes a tax issue on the return (the landing raises it).

Revision ID: 1017
Revises: 1016
"""

from __future__ import annotations

from alembic import op

revision = "1017"
down_revision = "1016"
branch_labels = None
depends_on = None

_SCHEDULES_BEFORE = "('fixed_assets', 'accrued_liabilities', 'passed_adjustments')"
_SCHEDULES_AFTER = (
    "('fixed_assets', 'accrued_liabilities', 'passed_adjustments', 'prepaid_expenses', "
    "'deferred_revenue', 'shareholder_distributions')"
)
_ITEMS_BEFORE = "('passed_adjustment', 'book_tax_expense')"
_ITEMS_AFTER = "('passed_adjustment', 'book_tax_expense', 'close_issue')"


def _swap(table: str, column: str, kinds: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_{column}_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_check CHECK ({column} IN {kinds})"
    )


def upgrade() -> None:
    _swap("tb_handoff_schedules", "kind", _SCHEDULES_AFTER)
    _swap("tb_handoff_tax_items", "item_kind", _ITEMS_AFTER)


def downgrade() -> None:
    # A hand-off that carried the new kinds keeps them: the swap back fails rather than drop rows.
    _swap("tb_handoff_tax_items", "item_kind", _ITEMS_BEFORE)
    _swap("tb_handoff_schedules", "kind", _SCHEDULES_BEFORE)
