"""The Accrued trial balance template is an import (A-02-T22; TASK-1470; DEC-610).

0149 generated `ledger_snapshots.source_kind` from `source` by an explicit list of the SPEC-028
import formats. A-02-T22 adds the template format, whose snapshots carry the source
`import_accrued_template`; they are `import`, not `other`. A generated column's expression can't
be altered in place, so the column is dropped and re-added with the new list (a stored generated
column rewrites the table without DML: no row is updated and the ADR-004 triggers never fire).

As 0149 requires, the upgrade first proves that no stored row changes kind: the old and the new
expressions differ only for `import_accrued_template`, so it refuses to run while any snapshot
carries that source (none can exist before this revision ships the format). The downgrade refuses
on the same condition, since those snapshots would read `other` again.

Revision ID: 0235
Revises: 0220
"""

from __future__ import annotations

from alembic import op

revision = "0235"
down_revision = "0220"
branch_labels = None
depends_on = None

_IMPORTS_0149 = (
    "'import_qbo_tb_csv', 'import_xero_tb_xlsx', 'import_qbd_tb_xlsx', "
    "'import_netsuite_tb_csv', 'import_intacct_tb_csv'"
)
_TEMPLATE = "import_accrued_template"


def _column(imports: str) -> str:
    return (
        "ALTER TABLE ledger_snapshots ADD COLUMN source_kind text "
        "GENERATED ALWAYS AS ("
        f"CASE WHEN source IN ({imports}) THEN 'import' "
        "WHEN source = 'fake' THEN 'fake' ELSE 'other' END"
        ") STORED"
    )


_REFUSE = (
    "DO $$ BEGIN "
    "IF EXISTS (SELECT 1 FROM ledger_snapshots WHERE source = 'import_accrued_template') "
    "THEN RAISE EXCEPTION 'refusing to run 0235: a ledger snapshot''s source_kind would change "
    "(ADR-004, 0149)'; "
    "END IF; END $$"
)


def _refuse_while_template_rows() -> None:
    # Forced row-level security hides every row from the owner here (no tenant is set): lift
    # FORCE for this transaction only to look, then put it back (0009's pattern, as 0149).
    op.execute("ALTER TABLE ledger_snapshots NO FORCE ROW LEVEL SECURITY")
    op.execute(_REFUSE)
    op.execute("ALTER TABLE ledger_snapshots FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    _refuse_while_template_rows()
    op.execute("ALTER TABLE ledger_snapshots DROP COLUMN source_kind")
    op.execute(_column(f"{_IMPORTS_0149}, '{_TEMPLATE}'"))


def downgrade() -> None:
    _refuse_while_template_rows()
    op.execute("ALTER TABLE ledger_snapshots DROP COLUMN source_kind")
    op.execute(_column(_IMPORTS_0149))
