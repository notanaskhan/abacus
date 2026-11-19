"""C-02-T19 (TASK-8708; DEC-5705; ADR-344 §3; red): the `ledger_write_pause` platform control,
expand-only.

ADR-344 names the per-firm kill switch `write.ledger.post_journal_entries`; platform controls are
named in snake case, so it is `ledger_write_pause` here, per firm or platform-wide (unkeyed). While
it is on, the W1 gate refuses the next write (`write_capability_disabled`): the reader is
uncached, so a flip takes effect within one call. No row is written: the control is inactive until
an operator sets it through `set_platform_control` (or a `verify_mismatch` sets it, C-02-T19).

Downgrade removes any `ledger_write_pause` row and narrows `platform_controls`' CHECK; the change
history is insert-only, so its CHECK keeps the name (0156's precedent).

Revision ID: 0981
Revises: 0980
"""

from __future__ import annotations

from alembic import op

revision = "0981"
down_revision = "0980"
branch_labels = None
depends_on = None

_CONTROLS = (
    "'ai_pause', 'model_route_block', 'email_pause', 'read_only', 'portal_sign_in', "
    "'confirmation_links', 'integration_pause', 'destruction_execute'"
)
_HISTORY = f"{_CONTROLS}, 'portal_sign_in_disabled'"
_NEW = "'ledger_write_pause'"


def _controls_check(table: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_control_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_control_check CHECK (control IN ({values}))"
    )


def upgrade() -> None:
    _controls_check("platform_control_changes", f"{_HISTORY}, {_NEW}")
    _controls_check("platform_controls", f"{_CONTROLS}, {_NEW}")


def downgrade() -> None:
    op.execute("DELETE FROM platform_controls WHERE control = 'ledger_write_pause'")
    _controls_check("platform_controls", _CONTROLS)
