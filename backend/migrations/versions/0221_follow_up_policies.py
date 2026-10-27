"""The firm's follow-up policy (R-01-T24; R-01 §4.2; DEC-74, DEC-563).

- `follow_up_policies` (new, communications, forced RLS): one row per firm, the policy POR-20's
  Reminder schedule and ADM-10's Reminders show: cadence in days (1 to 30, default 7), at most
  how many reminders (1 to 4, default 4), the recipient's local send time (default 09:00),
  weekdays only, stop when the client marks the binder done, tell the preparer after the last,
  copy the assigned preparer, and the mode (`draft_for_person`, the default: a person sends;
  `send_on_schedule`: the system sends from the published Reminder, only while
  `follow_ups.scheduled_send` is on for the firm). `version` is the row's optimistic-lock
  counter. A firm without a row reads the defaults. The app inserts and updates the policy
  columns; nothing deletes a row.

No firm content is written here (AGENTS 16): the policy is set through the portal settings.

Revision ID: 0221
Revises: 0220
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0221"
down_revision = "0220"
branch_labels = None
depends_on = None

_POLICY = (
    "cadence_days",
    "max_reminders",
    "send_local_time",
    "weekdays_only",
    "stop_on_binder_done",
    "notify_preparer_after_max",
    "cc_assigned_preparer",
    "mode",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE follow_up_policies (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            cadence_days integer NOT NULL DEFAULT 7 CHECK (cadence_days BETWEEN 1 AND 30),
            max_reminders integer NOT NULL DEFAULT 4 CHECK (max_reminders BETWEEN 1 AND 4),
            send_local_time time NOT NULL DEFAULT '09:00'
                CHECK (send_local_time = date_trunc('minute', send_local_time)),
            weekdays_only boolean NOT NULL DEFAULT true,
            stop_on_binder_done boolean NOT NULL DEFAULT true,
            notify_preparer_after_max boolean NOT NULL DEFAULT true,
            cc_assigned_preparer boolean NOT NULL DEFAULT false,
            mode text NOT NULL DEFAULT 'draft_for_person'
                CHECK (mode IN ('draft_for_person', 'send_on_schedule')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, updated_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "follow_up_policies")
    op.execute("REVOKE UPDATE, DELETE ON follow_up_policies FROM abacus_app")
    insert_columns(op, "follow_up_policies", ("tenant_id", *_POLICY, "updated_by"))
    op.execute(
        f"GRANT UPDATE ({', '.join((*_POLICY, 'version', 'updated_by', 'updated_at'))}) "
        "ON follow_up_policies TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE follow_up_policies")
