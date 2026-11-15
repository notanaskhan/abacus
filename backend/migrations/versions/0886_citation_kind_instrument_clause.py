"""T-07-T11 (S45; TASK-8038; ADR-343; SPEC-656 AC-1.4, AC-6.2; red): the eleventh citation kind,
`instrument_clause`, expand-only.

`citations.kind` is a text column with a CHECK over the kinds (0109); this widens the CHECK by one
kind and changes nothing else: no row is rewritten, the insert-only trigger, the human-only relink
CHECK and the match-id columns stand as ADR-166 wrote them. The kind's locator holds ids only
(`instrument_id`, `segmentation_id`, `clause_id`) and the quote's hash; no instrument text is
stored anywhere (ADR-343 §2).

Revision ID: 0886
Revises: 0885
"""

from __future__ import annotations

from alembic import op

revision = "0886"
down_revision = "0885"
branch_labels = None
depends_on = None

_TEN = (
    "'document_text', 'sheet_cell', 'ledger_line', 'workpaper_cell', 'methodology_step', "
    "'policy_rule', 'record_field', 'tax_form_line', 'artifact_cell', 'request_item'"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE citations DROP CONSTRAINT citations_kind_check, "
        f"ADD CONSTRAINT citations_kind_check CHECK (kind IN ({_TEN}, 'instrument_clause'))"
    )


def downgrade() -> None:
    # A downgrade with clause citations recorded fails on the CHECK: they are never deleted.
    op.execute(
        "ALTER TABLE citations DROP CONSTRAINT citations_kind_check, "
        f"ADD CONSTRAINT citations_kind_check CHECK (kind IN ({_TEN}))"
    )
