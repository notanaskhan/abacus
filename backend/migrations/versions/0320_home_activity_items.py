"""HOME-01's client activity projection (I-01-T12; I-01 §4.2 `NNNN_home_activity_items`; DEC-900).

New `home_activity_items`: one row per allowlisted outbox event (`practice/activity.py`), written
by the `HomeActivityProjector` consumer and pruned after 90 days. A rebuildable projection, never
the record of anything. Rows hold identifiers, enum codes and counts only: no names, no amounts,
no free text (`facts` is a flat object of short codes, ids, integers and booleans, size-capped);
names are resolved at read time through organisations and engagements. `source_event_id` is the
outbox event's id, unique per firm, so a redelivered or replayed event inserts nothing.

The app role may insert and delete (the prune), never update.

Revision ID: 0320
Revises: 0291
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0320"
down_revision = "0291"
branch_labels = None
depends_on = None

# The allowlist (`practice.activity.ACTIVITY_TYPES`); a new source extends it in a new migration.
_TYPES = ("client_upload", "follow_up_sent", "letter_recorded", "agent_pre_screen")


def upgrade() -> None:
    types = ", ".join(f"'{t}'" for t in _TYPES)
    op.execute(
        f"""
        CREATE TABLE home_activity_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            source_event_id uuid NOT NULL,
            event_type text NOT NULL CHECK (event_type IN ({types})),
            occurred_at timestamptz NOT NULL,
            client_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NULL,
            office_id uuid NULL,
            actor_kind text NOT NULL
                CHECK (actor_kind IN ('user', 'contact', 'agent_run', 'system')),
            actor_ref jsonb NOT NULL
                CHECK (jsonb_typeof(actor_ref) = 'object'
                       AND octet_length(actor_ref::text) <= 256),
            subject_ref jsonb NOT NULL
                CHECK (jsonb_typeof(subject_ref) = 'object'
                       AND octet_length(subject_ref::text) <= 256),
            facts jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(facts) = 'object' AND octet_length(facts::text) <= 512),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT home_activity_items_once UNIQUE (tenant_id, source_event_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX home_activity_items_recent ON home_activity_items "
        "(tenant_id, occurred_at DESC)"
    )
    tenant_table(op, "home_activity_items")
    op.execute("REVOKE UPDATE ON home_activity_items FROM abacus_app")
    op.execute("GRANT DELETE ON home_activity_items TO abacus_app")
    insert_columns(
        op,
        "home_activity_items",
        (
            "tenant_id",
            "source_event_id",
            "event_type",
            "occurred_at",
            "client_id",
            "engagement_id",
            "work_item_id",
            "office_id",
            "actor_kind",
            "actor_ref",
            "subject_ref",
            "facts",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE home_activity_items")
