"""I-01-T23: `home_activity_items.event_type` takes inbound mail and envelopes.

The allowlist grows by three codes (`practice.activity.ACTIVITY_TYPES`); the table holds no new
kind of data: identifiers, codes and counts only.

Revision ID: 0687
Revises: 0686
"""

from __future__ import annotations

from alembic import op

revision = "0687"
down_revision = "0686"
branch_labels = None
depends_on = None

_OLD = ("client_upload", "follow_up_sent", "letter_recorded", "agent_pre_screen")
_NEW = (*_OLD, "inbound_mail", "envelope_sent", "envelope_completed")
_NAME = "home_activity_items_event_type_check"


def _check(types: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{t}'" for t in types)
    op.execute(f"ALTER TABLE home_activity_items DROP CONSTRAINT {_NAME}")
    op.execute(
        f"ALTER TABLE home_activity_items ADD CONSTRAINT {_NAME} CHECK (event_type IN ({allowed}))"
    )


def upgrade() -> None:
    _check(_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM home_activity_items "
        "WHERE event_type IN ('inbound_mail', 'envelope_sent', 'envelope_completed')"
    )
    _check(_OLD)
