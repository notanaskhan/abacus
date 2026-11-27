"""An amendment's return names its original when it is inserted (T-08-T30, TASK-9005; DEC-6011).

0403 added `tax_returns.amends_return_id` (and the `1040x` form), and 0961 froze it on an accepted
return, but no migration granted `abacus_app` the column: not for INSERT (0089's list predates it)
and not for UPDATE (0403's `RETURN_UPDATE`), so an amendment could never be linked to the return
it amends. This grants INSERT on that one column. It is set once, when the amendment's return is
created (`tax.kind` from the work item's details), never updated (no UPDATE grant), and 0961's
`tax_return_accepted_frozen` keeps it fixed once the amendment is accepted.
"""

from __future__ import annotations

from alembic import op

revision = "1033"
down_revision = "1032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT INSERT (amends_return_id) ON tax_returns TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (amends_return_id) ON tax_returns FROM abacus_app")
