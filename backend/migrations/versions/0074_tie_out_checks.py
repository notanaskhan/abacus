"""Tie-out checks on the trial balance of record (SPEC-310; TASK-321; A-02-T11).

- `tie_out_checks`: a named check on a target (a trial balance), keyed per target; the pointer
  to its current definition is its only updatable column.
- `tie_out_check_versions` (insert-only): each definition. An expected value must cite its
  source (CHECK); only a human defines one (CHECK). Results are computed on read, never stored.

Revision ID: 0074
Revises: 0073
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tie_out_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            target_type text NOT NULL CHECK (target_type = 'trial_balance'),
            target_id uuid NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
            kind text NOT NULL CHECK (kind IN ('balanced', 'tie', 'rollforward')),
            current_version_no integer NOT NULL DEFAULT 1 CHECK (current_version_no > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, target_id, key),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    tenant_table(op, "tie_out_checks")
    op.execute("REVOKE UPDATE, DELETE ON tie_out_checks FROM abacus_app")
    op.execute("GRANT UPDATE (current_version_no) ON tie_out_checks TO abacus_app")
    insert_columns(
        op,
        "tie_out_checks",
        ("tenant_id", "engagement_id", "target_type", "target_id", "key", "kind", "created_by"),
    )
    op.execute(
        """
        CREATE TABLE tie_out_check_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            check_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no > 0),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
            actual_selector jsonb NOT NULL,
            expected jsonb NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            tolerance numeric(20, 2) NOT NULL DEFAULT 0.00 CHECK (tolerance >= 0),
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 500),
            created_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, check_id, version_no),
            CHECK (expected IS NULL OR cardinality(citation_ids) > 0),
            CHECK (version_no = 1 OR reason IS NOT NULL),
            FOREIGN KEY (tenant_id, check_id) REFERENCES tie_out_checks (tenant_id, id)
        )
        """
    )
    tenant_table(op, "tie_out_check_versions")
    op.execute("REVOKE UPDATE, DELETE ON tie_out_check_versions FROM abacus_app")
    insert_columns(
        op,
        "tie_out_check_versions",
        (
            "tenant_id",
            "check_id",
            "version_no",
            "label",
            "actual_selector",
            "expected",
            "citation_ids",
            "tolerance",
            "reason",
            "created_by",
            "actor_kind",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE tie_out_check_versions")
    op.execute("DROP TABLE tie_out_checks")
