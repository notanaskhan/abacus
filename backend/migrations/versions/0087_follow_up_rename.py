"""Reminders become follow-ups (F-03-T16; DEC-74 rename only; glossary "Follow-up").

`reminders` → `follow_up_schedules`, `reminder_items` → `follow_up_items` and its `reminder_id`
→ `follow_up_id` (with the index); grants, policies and constraints follow the tables. Stored
values (event types, audit actions and target type) keep their wording, so past rows still read.

Revision ID: 0087
Revises: 0086
"""

from __future__ import annotations

from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reminders RENAME TO follow_up_schedules")
    op.execute("ALTER TABLE reminder_items RENAME TO follow_up_items")
    op.execute("ALTER TABLE follow_up_items RENAME COLUMN reminder_id TO follow_up_id")
    op.execute("ALTER INDEX reminder_items_item RENAME TO follow_up_items_item")


def downgrade() -> None:
    op.execute("ALTER INDEX follow_up_items_item RENAME TO reminder_items_item")
    op.execute("ALTER TABLE follow_up_items RENAME COLUMN follow_up_id TO reminder_id")
    op.execute("ALTER TABLE follow_up_items RENAME TO reminder_items")
    op.execute("ALTER TABLE follow_up_schedules RENAME TO reminders")
