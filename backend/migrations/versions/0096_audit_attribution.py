"""Audit attribution (Q-02-T16).

`audit_events` gains four columns:
- `engagement_id` and `work_item_id`: the scope `tx.record` names. Indexed, so the audit
  explorer filters exactly (DEC-121's follow-up).
- `on_behalf_of_user_id`: the person an agent or the platform acted for.
- `policy_ref`: the policy a `policy` actor applied.

Two new rules:
- `actor_kind` may be `policy`, which stays dormant (DEC-53): a policy row needs a
  `policy_ref`, and no context can act as a policy yet.
- Every agent row names the person it acted for. The check is NOT VALID, so history from before
  this column is left as it is.

Revision ID: 0096
Revises: 0095
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None

_BEFORE = (
    "tenant_id",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
)
_AFTER = (*_BEFORE, "engagement_id", "work_item_id", "on_behalf_of_user_id", "policy_ref")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE audit_events
            ADD COLUMN engagement_id uuid NULL,
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN on_behalf_of_user_id uuid NULL,
            ADD COLUMN policy_ref text NULL CHECK (length(policy_ref) BETWEEN 1 AND 200)
        """
    )
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_kind_check")
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_kind_check "
        "CHECK (actor_kind IN ('human', 'agent', 'system', 'support', 'policy'))"
    )
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_policy_names_its_policy "
        "CHECK (actor_kind <> 'policy' OR policy_ref IS NOT NULL)"
    )
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_agent_acts_for_a_person "
        "CHECK (actor_kind <> 'agent' OR on_behalf_of_user_id IS NOT NULL) NOT VALID"
    )
    op.execute(
        "CREATE INDEX audit_events_engagement ON audit_events (tenant_id, engagement_id, seq) "
        "WHERE engagement_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX audit_events_work_item ON audit_events (tenant_id, work_item_id, seq) "
        "WHERE work_item_id IS NOT NULL"
    )
    insert_columns(op, "audit_events", _AFTER)


def downgrade() -> None:
    insert_columns(op, "audit_events", _BEFORE)
    op.execute("DROP INDEX audit_events_work_item")
    op.execute("DROP INDEX audit_events_engagement")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_agent_acts_for_a_person")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_policy_names_its_policy")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_kind_check")
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_kind_check "
        "CHECK (actor_kind IN ('human', 'agent', 'system', 'support'))"
    )
    op.execute(
        "ALTER TABLE audit_events DROP COLUMN policy_ref, DROP COLUMN on_behalf_of_user_id, "
        "DROP COLUMN work_item_id, DROP COLUMN engagement_id"
    )
