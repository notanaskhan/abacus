"""A-08-T03 (S45; TASK-8045; ADR-157 proposed, ADR-152 amendment; SPEC-657 AC-7.6; red): the
`confirmation_links` platform control, expand-only.

`platform_controls.control` and `platform_control_changes.control` are text columns with a CHECK
over the control names (0086, widened by 0156). This adds one name, per firm and global, that
pauses the public `/v1/confirm/*` family and respondent link issuance (A-08 §4.8). No row is
written: a control is inactive until an operator sets it through `set_platform_control`.

Downgrade removes any `confirmation_links` row from `platform_controls` and narrows its CHECK;
the change history is insert-only, so its CHECK keeps the name (0156's precedent).

Revision ID: 0887
Revises: 0886
"""

from __future__ import annotations

from alembic import op

revision = "0887"
down_revision = "0886"
branch_labels = None
depends_on = None

_CONTROLS = "'ai_pause', 'model_route_block', 'email_pause', 'read_only', 'portal_sign_in'"
_HISTORY = f"{_CONTROLS}, 'portal_sign_in_disabled'"
_NEW = "'confirmation_links'"


def _controls_check(table: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_control_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_control_check CHECK (control IN ({values}))"
    )


def upgrade() -> None:
    _controls_check("platform_control_changes", f"{_HISTORY}, {_NEW}")
    _controls_check("platform_controls", f"{_CONTROLS}, {_NEW}")


def downgrade() -> None:
    op.execute("DELETE FROM platform_controls WHERE control = 'confirmation_links'")
    _controls_check("platform_controls", _CONTROLS)
