"""A-04-T07 procedures, tailoring and pack references (A-04 §3.1 AC1.9, §6 AC6.1; DEC-1867):
expand-only.

- `program_procedures.row_version`: a tailoring names the version it saw (409 `version_conflict`);
  instantiation may write `linked_work` from the step's workpaper reference.
- `program_steps.template_refs`: the request and workpaper templates a step points at
  (`request:<key>`, `workpaper:<kind>`), read from a workbook's optional `templates` column.
  Pack validation resolves them against the pinned version and the firm's template library
  (OQ-15, DEC-1758) before a draft writes anything.

Revision ID: 0614
Revises: 0613
"""

from __future__ import annotations

from alembic import op

revision = "0614"
down_revision = "0613"
branch_labels = None
depends_on = None

_REFS = "^((request|workpaper):[a-z][a-z0-9_]{0,63}(;|$))*$"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE program_procedures "
        "ADD COLUMN row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1)"
    )
    # Instantiation writes a procedure's linked workpaper from its step's references.
    op.execute(
        "GRANT INSERT (linked_work), UPDATE (row_version) ON program_procedures TO abacus_app"
    )
    op.execute(
        "ALTER TABLE program_steps "
        "ADD COLUMN template_refs text[] NOT NULL DEFAULT '{}' "
        "CONSTRAINT program_steps_template_refs_shape CHECK ("
        f"cardinality(template_refs) <= 20 AND array_to_string(template_refs, ';') ~ '{_REFS}')"
    )
    op.execute(
        "GRANT INSERT (template_refs), UPDATE (template_refs) ON program_steps TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE INSERT (template_refs), UPDATE (template_refs) ON program_steps FROM abacus_app"
    )
    op.execute("ALTER TABLE program_steps DROP COLUMN template_refs")
    op.execute(
        "REVOKE INSERT (linked_work), UPDATE (row_version) ON program_procedures FROM abacus_app"
    )
    op.execute("ALTER TABLE program_procedures DROP COLUMN row_version")
