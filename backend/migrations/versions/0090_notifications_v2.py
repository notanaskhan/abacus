"""Notifications v2 (P-01-T03; SHL-04; C16).

- The kind CHECK from 0024 required a dot. It is dropped and re-created to allow the undotted
  C16 codes as well (`^[a-z][a-z_]*(\\.[a-z][a-z_]*)?$`), added NOT VALID then validated, before
  the backfill. Dotted SPEC-013 codes stay valid as legacy.
- Three kinds are renamed to the chapter 03 §6.4 codes the tabs need, with a backfill:
  `evidence.uploaded` to `client_uploaded`, `comment.mentioned` to `mention`, `review.assigned`
  to `review_assigned`.
- `notifications` gains `category`, `actor_user_id`, `actor_kind`, `client_id` and
  `work_item_id` (the P-06 scope re-check). Existing rows get their kind's category.
- The recipient index gains `id` for the keyset.
- New `notification_preferences` (per person, per kind) and `notification_deliveries` (one row
  per notification per channel; email only), both tenant tables with forced RLS. Rows hold
  identifiers and codes only.

Revision ID: 0090
Revises: 0089
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None

_KIND = "^[a-z][a-z_]*(\\.[a-z][a-z_]*)?$"
_DOTTED = "^[a-z][a-z_]*\\.[a-z][a-z_]*$"
_RENAMES = (
    ("evidence.uploaded", "client_uploaded"),
    ("comment.mentioned", "mention"),
    ("review.assigned", "review_assigned"),
)
_CATEGORIES = {
    "approval": (
        "review_assigned",
        "materiality.proposed",
        "risk.approval_requested",
        "finding.severity_proposed",
        "independence.requested",
        "reminders.drafted",
    ),
    "mention": ("mention",),
    "client_activity": ("client_uploaded", "connection.created", "connection.revoked"),
    "system": (
        "support_session.requested",
        "support_session.emergency_approved",
        "budget.soft_crossed",
        "budget.anomaly",
    ),
}
_CATEGORY = "('approval','mention','client_activity','run','deadline','system','other')"


def _kind_check(pattern: str) -> None:
    op.execute("ALTER TABLE notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind ~ '{pattern}') NOT VALID"
    )
    op.execute("ALTER TABLE notifications VALIDATE CONSTRAINT notifications_kind_check")


def _rename(old: str, new: str) -> None:
    op.execute(
        sa.text("UPDATE notifications SET kind = :new WHERE kind = :old").bindparams(
            new=new, old=old
        )
    )


def upgrade() -> None:
    _kind_check(_KIND)
    for old, new in _RENAMES:
        _rename(old, new)
    op.execute(
        f"""
        ALTER TABLE notifications
            ADD COLUMN category text NOT NULL DEFAULT 'other' CHECK (category IN {_CATEGORY}),
            ADD COLUMN actor_user_id uuid NULL,
            ADD COLUMN actor_kind text NULL
                CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')),
            ADD COLUMN client_id uuid NULL,
            ADD COLUMN work_item_id uuid NULL
        """
    )
    for category, kinds in _CATEGORIES.items():
        for kind in kinds:
            op.execute(
                sa.text(
                    "UPDATE notifications SET category = :category WHERE kind = :kind"
                ).bindparams(category=category, kind=kind)
            )
    op.execute("DROP INDEX notifications_recipient")
    op.execute(
        "CREATE INDEX notifications_recipient ON notifications "
        "(tenant_id, recipient_user_id, created_at DESC, id)"
    )
    insert_columns(
        op,
        "notifications",
        (
            "id",
            "tenant_id",
            "recipient_user_id",
            "kind",
            "event_id",
            "engagement_id",
            "subject_type",
            "subject_id",
            "category",
            "actor_user_id",
            "actor_kind",
            "client_id",
            "work_item_id",
        ),
    )

    op.execute(
        f"""
        CREATE TABLE notification_preferences (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind ~ '{_KIND}'),
            in_app boolean NOT NULL DEFAULT true,
            email boolean NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, user_id, kind),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "notification_preferences")
    op.execute("REVOKE UPDATE, DELETE ON notification_preferences FROM abacus_app")
    insert_columns(
        op, "notification_preferences", ("tenant_id", "user_id", "kind", "in_app", "email")
    )
    op.execute(
        "GRANT UPDATE (in_app, email, updated_at) ON notification_preferences TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE notification_deliveries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            notification_id uuid NOT NULL REFERENCES notifications (id) ON DELETE CASCADE,
            channel text NOT NULL CHECK (channel IN ('email')),
            status text NOT NULL CHECK (status IN ('queued', 'sent', 'suppressed', 'failed')),
            message_ref text NULL CHECK (length(message_ref) <= 200),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT notification_deliveries_once UNIQUE (notification_id, channel)
        )
        """
    )
    op.execute(
        "CREATE INDEX notification_deliveries_tenant ON notification_deliveries "
        "(tenant_id, created_at)"
    )
    tenant_table(op, "notification_deliveries")
    op.execute("REVOKE UPDATE, DELETE ON notification_deliveries FROM abacus_app")
    insert_columns(
        op, "notification_deliveries", ("tenant_id", "notification_id", "channel", "status")
    )
    op.execute("GRANT UPDATE (status, message_ref) ON notification_deliveries TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE notification_deliveries")
    op.execute("DROP TABLE notification_preferences")
    insert_columns(
        op,
        "notifications",
        (
            "id",
            "tenant_id",
            "recipient_user_id",
            "kind",
            "event_id",
            "engagement_id",
            "subject_type",
            "subject_id",
        ),
    )
    op.execute("DROP INDEX notifications_recipient")
    op.execute(
        "CREATE INDEX notifications_recipient ON notifications "
        "(tenant_id, recipient_user_id, created_at DESC)"
    )
    op.execute(
        "ALTER TABLE notifications DROP COLUMN work_item_id, DROP COLUMN client_id, "
        "DROP COLUMN actor_kind, DROP COLUMN actor_user_id, DROP COLUMN category"
    )
    for old, new in _RENAMES:
        _rename(new, old)
    _kind_check(_DOTTED)
