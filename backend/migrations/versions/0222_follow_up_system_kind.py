"""A scheduled Reminder is recorded as the system's (R-01-T24 review L1; DEC-566, DEC-568).

0128 limits `follow_up_schedules.drafted_by_kind` to `person` and `agent`. A Reminder the system
sends on the firm's schedule (`send_on_schedule`, behind `follow_ups.scheduled_send`) is neither:
its words are the firm's published template and no person sent it. The check gains `system`.
0128 is on main and is not edited: its column check is replaced here.

Revision ID: 0222
Revises: 0221
"""

from __future__ import annotations

from alembic import op

revision = "0222"
down_revision = "0221"
branch_labels = None
depends_on = None

_NAME = "follow_up_schedules_drafted_by_kind_check"


def upgrade() -> None:
    op.execute(f"ALTER TABLE follow_up_schedules DROP CONSTRAINT {_NAME}")
    op.execute(
        f"ALTER TABLE follow_up_schedules ADD CONSTRAINT {_NAME} "
        "CHECK (drafted_by_kind IN ('person', 'agent', 'system'))"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM follow_up_schedules "
        "WHERE drafted_by_kind = 'system') THEN RAISE EXCEPTION "
        "'scheduled Reminders were recorded: 0222 cannot be undone'; END IF; END $$"
    )
    op.execute(f"ALTER TABLE follow_up_schedules DROP CONSTRAINT {_NAME}")
    op.execute(
        f"ALTER TABLE follow_up_schedules ADD CONSTRAINT {_NAME} "
        "CHECK (drafted_by_kind IN ('person', 'agent'))"
    )
