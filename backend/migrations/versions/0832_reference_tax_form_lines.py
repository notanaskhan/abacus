"""T-05-T21 (S38; TASK-7409; T-05 §4.2; C21 additive; DEC-4408): the `tax_form_lines` reference
kind, expand-only.

`reference_sets.kind` admits `tax_form_lines`: a Form 1065 line set per tax year (Schedule L, K,
Form 8825, M-1, M-2 and the M-3 keys), drafted and published through migration 0400's owner-only
definers by two people, like every other reference kind. Rows are public law, loaded by the
operator CLI from a reviewed draft, never by a migration or a seed (AGENTS 16). Widening a CHECK
is additive; no row changes.

Revision ID: 0832
Revises: 0831
"""

from __future__ import annotations

from alembic import op

revision = "0832"
down_revision = "0831"
branch_labels = None
depends_on = None

_BEFORE = (
    "'due_date_rules', 'legal_holidays', 'disaster_postponements', 'form_8879_set', "
    "'information_return_thresholds', 'retention_minimums', 'standards_sets', "
    "'state_breach_matrix', 'state_retention_rules'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE reference_sets DROP CONSTRAINT reference_sets_kind_check")
    op.execute(
        "ALTER TABLE reference_sets ADD CONSTRAINT reference_sets_kind_check "
        f"CHECK (kind IN ({_BEFORE}, 'tax_form_lines'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE reference_sets DROP CONSTRAINT reference_sets_kind_check")
    op.execute(
        "ALTER TABLE reference_sets ADD CONSTRAINT reference_sets_kind_check "
        f"CHECK (kind IN ({_BEFORE}))"
    )
