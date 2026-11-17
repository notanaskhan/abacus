"""W-01-T07 rest (TASK-8446; DEC-5433; ADR-157; SPEC-659 AC-4, OQ-9; red): the
`integration_pause` platform control, keyed by the catalogue key, expand-only.

`platform_controls.control` and `platform_control_changes.control` carry a CHECK over the control
names (0086, widened by 0156 and 0887). This adds `integration_pause`, per firm or platform-wide.
Its key is the integration's catalogue key, kept in the `route` column: 0086's keyed-column CHECK
`(control = 'model_route_block') = (route IS NOT NULL)` becomes the same rule over both keyed
controls. No row is written: a control is inactive until an operator sets it through
`set_platform_control`.

Downgrade removes any `integration_pause` row from `platform_controls` and narrows its CHECKs;
the change history is insert-only, so its CHECKs keep the name (0156's precedent).

Revision ID: 0948
Revises: 0947
"""

from __future__ import annotations

from alembic import op

revision = "0948"
down_revision = "0947"
branch_labels = None
depends_on = None

_CONTROLS = (
    "'ai_pause', 'model_route_block', 'email_pause', 'read_only', 'portal_sign_in', "
    "'confirmation_links'"
)
_HISTORY = f"{_CONTROLS}, 'portal_sign_in_disabled'"
_NEW = "'integration_pause'"


def _controls_check(table: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_control_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_control_check CHECK (control IN ({values}))"
    )


def _keyed_check(table: str, keyed: str) -> None:
    """Replace the keyed-column CHECK (0086's is unnamed; this one is `<table>_route_check`)."""
    op.execute(
        f"""
        DO $$
        DECLARE c text;
        BEGIN
            FOR c IN
                SELECT conname FROM pg_constraint
                 WHERE conrelid = '{table}'::regclass AND contype = 'c'
                   AND pg_get_constraintdef(oid) LIKE '%route IS NOT NULL%'
            LOOP
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', c);
            END LOOP;
        END $$
        """  # noqa: S608 -- fixed SQL over this module's table names, no input
    )
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_route_check "
        f"CHECK ((control IN ({keyed})) = (route IS NOT NULL))"
    )


def upgrade() -> None:
    _controls_check("platform_control_changes", f"{_HISTORY}, {_NEW}")
    _controls_check("platform_controls", f"{_CONTROLS}, {_NEW}")
    for table in ("platform_control_changes", "platform_controls"):
        _keyed_check(table, f"'model_route_block', {_NEW}")


def downgrade() -> None:
    op.execute("DELETE FROM platform_controls WHERE control = 'integration_pause'")
    _keyed_check("platform_controls", "'model_route_block'")
    _controls_check("platform_controls", _CONTROLS)
