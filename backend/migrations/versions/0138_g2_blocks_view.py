"""G2 v2's stricter-only firm setting (P-07-T24; ADR-164 item 3, DEC-39).

- `firm_setting_values.key` (identity, migration 0081) also accepts `g2_blocks_view`: when a firm
  switches it on, team members not cleared for an attest client's engagement lose content reads
  too (TASK-045's stricter read gate). It never grants: no matrix cell may name it
  (`authz.matrix.STRICTER_SETTING_KEYS`).

Rows are set by the firm administrator (`firm_settings.set_firm_setting`) or the scenario loader,
never here. Downgrade removes any `g2_blocks_view` row and restores 0081's list.

Revision ID: 0138
Revises: 0133
"""

from __future__ import annotations

from alembic import op

revision = "0138"
down_revision = "0133"
branch_labels = None
depends_on = None

_BEFORE = (
    "('seniors_can_accept', 'seniors_can_create', 'seniors_can_publish', "
    "'client_service_can_publish', 'staff_can_accept_evidence')"
)
_AFTER = (
    "('seniors_can_accept', 'seniors_can_create', 'seniors_can_publish', "
    "'client_service_can_publish', 'staff_can_accept_evidence', 'g2_blocks_view')"
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
    op.execute("DELETE FROM firm_setting_values WHERE key = 'g2_blocks_view'")
    _check(_BEFORE)
