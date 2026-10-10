"""Due dates, the firm's time zone, and overdue reminders (SPEC-027; TASK-051).

- `request_items.due_on`, `request_lists.default_due_on`: an item is due on its own date, else
  its list's.
- `firms.time_zone`: the engagement agent's daily tick runs at 09:00 there, on business days.
- `reminders` / `reminder_items`: each reminder the agent sent or drafted, and the items it named
  with their due date at the time, so the caps survive restarts and a changed due date starts the
  sequence again.
- `engagement_agents.self_paused_reason`: the agent pauses itself when the engagement has no
  active partner to act for (SPEC-027 AC-8).

Revision ID: 0040
Revises: 0039
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE request_items ADD COLUMN due_on date NULL")
    op.execute("ALTER TABLE request_lists ADD COLUMN default_due_on date NULL")
    op.execute("GRANT UPDATE (due_on) ON request_items TO abacus_app")
    op.execute("GRANT UPDATE (default_due_on) ON request_lists TO abacus_app")
    op.execute(
        "ALTER TABLE firms ADD COLUMN time_zone text NOT NULL DEFAULT 'America/New_York' "
        "CHECK (time_zone ~ '^[A-Za-z_]+(/[A-Za-z0-9_+-]+)*$' AND length(time_zone) <= 64)"
    )
    op.execute("GRANT UPDATE (time_zone) ON firms TO abacus_app")
    op.execute(
        "ALTER TABLE engagement_agents ADD COLUMN self_paused_reason text NULL "
        "CHECK (self_paused_reason ~ '^[a-z_]+$')"
    )
    op.execute("GRANT UPDATE (self_paused_reason) ON engagement_agents TO abacus_app")
    op.execute(
        """
        CREATE TABLE reminders (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            recipient_user_id uuid NOT NULL,
            status text NOT NULL CHECK (status IN ('drafted', 'sent', 'dismissed')),
            note text NULL CHECK (length(note) BETWEEN 1 AND 500),
            agent_run_id uuid NULL,
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE reminder_items (
            tenant_id uuid NOT NULL,
            reminder_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            due_on date NOT NULL,
            sequence integer NOT NULL CHECK (sequence BETWEEN 1 AND 3),
            PRIMARY KEY (tenant_id, reminder_id, request_item_id),
            FOREIGN KEY (tenant_id, reminder_id) REFERENCES reminders (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX reminder_items_item ON reminder_items (tenant_id, request_item_id)")
    for table in ("reminders", "reminder_items"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON reminders FROM abacus_app")
    insert_columns(
        op,
        "reminders",
        ("tenant_id", "engagement_id", "recipient_user_id", "status", "note", "agent_run_id"),
    )
    op.execute("GRANT UPDATE (status, note, decided_by, decided_at) ON reminders TO abacus_app")
    op.execute("REVOKE UPDATE, DELETE ON reminder_items FROM abacus_app")
    insert_columns(
        op, "reminder_items", ("tenant_id", "reminder_id", "request_item_id", "due_on", "sequence")
    )


def downgrade() -> None:
    op.execute("DROP TABLE reminder_items")
    op.execute("DROP TABLE reminders")
    op.execute("REVOKE UPDATE (self_paused_reason) ON engagement_agents FROM abacus_app")
    op.execute("ALTER TABLE engagement_agents DROP COLUMN self_paused_reason")
    op.execute("REVOKE UPDATE (time_zone) ON firms FROM abacus_app")
    op.execute("ALTER TABLE firms DROP COLUMN time_zone")
    op.execute("REVOKE UPDATE (default_due_on) ON request_lists FROM abacus_app")
    op.execute("REVOKE UPDATE (due_on) ON request_items FROM abacus_app")
    op.execute("ALTER TABLE request_lists DROP COLUMN default_due_on")
    op.execute("ALTER TABLE request_items DROP COLUMN due_on")
