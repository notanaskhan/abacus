"""Sample expansions (A-08-T17; A-08 §3 F3; SPEC-657 AC-3.1 to AC-3.4; AUD-12 f to h; DEC-5307).

`sample_expansions`: a person's request to add items to an approved sample-set version, with a
required rationale and a named approver who is not the requester; only that approver decides,
and only a person (the CHECKs hold it too). An approved expansion names the new sample-set
version it appended (the first items keep their positions; the draw honours the prefix).

Revision ID: 0931
Revises: 0930
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0931"
down_revision = "0930"
branch_labels = None
depends_on = None

INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "sample_set_id", "base_version_id",
    "base_count", "add_by_score", "add_unpredictable", "add_item_keys", "rationale",
    "rationale_suggestion_id", "requested_by", "approver_user_id", "content_hash",
)  # fmt: skip
UPDATES = ("status", "decided_by", "decided_actor_kind", "decided_at", "resulting_version_id")
# AC-3.4 (DEC-5327): an expansion's named keys ("Add participants") carry their own reason.
_REASONS_BEFORE = "('random', 'threshold', 'risk_score', 'unpredictable')"
_REASONS_AFTER = "('random', 'threshold', 'risk_score', 'unpredictable', 'named')"


def _reasons(values: str) -> None:
    op.execute("ALTER TABLE sample_items DROP CONSTRAINT sample_items_selection_reason_check")
    op.execute(
        "ALTER TABLE sample_items ADD CONSTRAINT sample_items_selection_reason_check "
        f"CHECK (selection_reason IN {values})"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sample_expansions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            sample_set_id uuid NOT NULL,
            base_version_id uuid NOT NULL,
            base_count integer NOT NULL CHECK (base_count >= 0),
            add_by_score integer NOT NULL DEFAULT 0 CHECK (add_by_score BETWEEN 0 AND 500),
            add_unpredictable integer NOT NULL DEFAULT 0
                CHECK (add_unpredictable BETWEEN 0 AND 500),
            add_item_keys text[] NOT NULL DEFAULT '{}' CHECK (cardinality(add_item_keys) <= 500),
            rationale text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 1 AND 2000),
            rationale_suggestion_id uuid NULL,
            requested_by uuid NOT NULL,
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            approver_user_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'pending_approval'
                CHECK (status IN ('pending_approval', 'approved', 'rejected', 'withdrawn')),
            decided_by uuid NULL,
            decided_actor_kind text NULL CHECK (decided_actor_kind = 'human'),
            decided_at timestamptz NULL,
            resulting_version_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            UNIQUE (tenant_id, id),
            CHECK (add_by_score + add_unpredictable + cardinality(add_item_keys) > 0),
            -- The requester never approves their own expansion; the named approver decides.
            CHECK (approver_user_id <> requested_by),
            CHECK ((status IN ('approved', 'rejected')) = (decided_by IS NOT NULL)),
            CHECK (decided_by IS NULL OR (decided_by = approver_user_id
                AND decided_actor_kind = 'human' AND decided_at IS NOT NULL)),
            CHECK ((status = 'approved') = (resulting_version_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, sample_set_id) REFERENCES sample_sets (tenant_id, id),
            FOREIGN KEY (tenant_id, base_version_id)
                REFERENCES sample_set_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, resulting_version_id)
                REFERENCES sample_set_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, requested_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, approver_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX sample_expansions_one_open ON sample_expansions "
        "(tenant_id, sample_set_id) WHERE status = 'pending_approval'"
    )
    tenant_table(op, "sample_expansions")
    insert_columns(op, "sample_expansions", INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON sample_expansions FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON sample_expansions TO abacus_app")
    _reasons(_REASONS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM sample_items WHERE selection_reason = 'named'")
    _reasons(_REASONS_BEFORE)
    op.execute("DROP TABLE sample_expansions")
