"""P-07-T15: the firm setting `allow_letter_exceptions` (P-07 §4; OQ-9, DEC-39, DEC-224).

`firm_setting_values.key` (identity, 0081; widened by 0138) also accepts
`allow_letter_exceptions`: when a firm switches it on, the engagement partner may record G3 as
"Not required this year" with a reason. It is not a matrix condition (no cell may name it,
`authz.matrix.POLICY_SETTING_KEYS`); the letter service reads it. Default off: no row.

Rows are set by the firm administrator (`firm_settings.set_firm_setting`), never here. Downgrade
removes any `allow_letter_exceptions` row and restores 0138's list.

Revision ID: 0182
Revises: 0181
"""

from __future__ import annotations

from alembic import op

revision = "0182"
down_revision = "0181"
branch_labels = None
depends_on = None

_BEFORE = (
    "('seniors_can_accept', 'seniors_can_create', 'seniors_can_publish', "
    "'client_service_can_publish', 'staff_can_accept_evidence', 'g2_blocks_view')"
)
_AFTER = (
    "('seniors_can_accept', 'seniors_can_create', 'seniors_can_publish', "
    "'client_service_can_publish', 'staff_can_accept_evidence', 'g2_blocks_view', "
    "'allow_letter_exceptions')"
)


def _check(keys: str) -> None:
    op.execute("ALTER TABLE firm_setting_values DROP CONSTRAINT firm_setting_values_key_check")
    op.execute(
        "ALTER TABLE firm_setting_values ADD CONSTRAINT firm_setting_values_key_check "
        f"CHECK (key IN {keys})"
    )


def upgrade() -> None:
    _check(_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM firm_setting_values WHERE key IN ('allow_letter_exceptions')")
    _check(_BEFORE)
