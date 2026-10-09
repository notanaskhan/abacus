"""Request items' classification (SPEC-022; TASK-038).

`dataset` is what an A item needs from the connected system; `tier_source` is where the tier came
from (a manual override, the firm's own tier, or a rule); `tier_rule` is the rule that matched.
The app classifies on insert and may reclassify or override later.

Revision ID: 0030
Revises: 0029
"""

from __future__ import annotations

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

_COLUMNS = "dataset, tier_source, tier_rule"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE request_items
            ADD COLUMN dataset text NULL CHECK (dataset ~ '^[a-z][a-z_]{0,49}$'),
            ADD COLUMN tier_source text NULL
                CHECK (tier_source IN ('override', 'methodology', 'rule')),
            ADD COLUMN tier_rule text NULL CHECK (tier_rule ~ '^[a-z]{1,10}-[0-9]{1,4}$'),
            ADD CONSTRAINT request_items_dataset_is_tier_a
                CHECK (dataset IS NULL OR retrievability_tier = 'A')
        """
    )
    # Items seeded before classification keep their tier, as the firm's own. The owner is subject
    # to forced row-level security, and the backfill spans every firm.
    op.execute("ALTER TABLE request_items NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE request_items SET tier_source = 'methodology' "
        "WHERE retrievability_tier IS NOT NULL"
    )
    op.execute("ALTER TABLE request_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_tier_has_source "
        "CHECK ((retrievability_tier IS NULL) = (tier_source IS NULL))"
    )
    op.execute(f"GRANT INSERT ({_COLUMNS}) ON request_items TO abacus_app")
    op.execute(f"GRANT UPDATE (retrievability_tier, {_COLUMNS}) ON request_items TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE (retrievability_tier, {_COLUMNS}) ON request_items FROM abacus_app")
    op.execute(f"REVOKE INSERT ({_COLUMNS}) ON request_items FROM abacus_app")
    op.execute(
        "ALTER TABLE request_items DROP CONSTRAINT request_items_dataset_is_tier_a, "
        "DROP CONSTRAINT request_items_tier_has_source, "
        "DROP COLUMN tier_rule, DROP COLUMN tier_source, DROP COLUMN dataset"
    )
