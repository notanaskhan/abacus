"""The trial balance of record, first slice (SPEC-309; TASK-320; A-02).

- `trial_balances`: one per work item, entity, label and period end. The pointer to the
  current version is its only updatable column.
- `trial_balance_versions` (insert-only): each adoption of an immutable ledger snapshot, with the
  prior-year snapshot it is paired with. Only a human adopts (CHECK); a re-adoption needs a reason.
- `trial_balance_annotations` (insert-only): an account's audit area and working-paper reference
  on a trial balance; the newest row per account counts. Amounts are never annotated (ADR-004).

Revision ID: 0073
Revises: 0072
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE trial_balances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            label text NOT NULL DEFAULT 'standard'
                CHECK (label IN ('standard', 'interim', 'prior', 'budget', 'preliminary')),
            period_start date NOT NULL,
            period_end date NOT NULL CHECK (period_end >= period_start),
            display_unit text NOT NULL DEFAULT 'cents'
                CHECK (display_unit IN ('cents', 'whole_dollars')),
            current_version_no integer NOT NULL DEFAULT 1 CHECK (current_version_no > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, id),
            UNIQUE (tenant_id, work_item_id, client_entity_id, label, period_end),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    tenant_table(op, "trial_balances")
    op.execute("REVOKE UPDATE, DELETE ON trial_balances FROM abacus_app")
    op.execute("GRANT UPDATE (current_version_no) ON trial_balances TO abacus_app")
    insert_columns(
        op,
        "trial_balances",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "client_entity_id",
            "label",
            "period_start",
            "period_end",
            "display_unit",
            "created_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE trial_balance_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            trial_balance_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no > 0),
            snapshot_id uuid NOT NULL,
            prior_snapshot_id uuid NULL,
            adopted_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 500),
            content_fingerprint text NOT NULL CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, trial_balance_id, version_no),
            CHECK (version_no = 1 OR reason IS NOT NULL),
            CHECK (prior_snapshot_id IS NULL OR prior_snapshot_id <> snapshot_id),
            FOREIGN KEY (tenant_id, client_entity_id, trial_balance_id)
                REFERENCES trial_balances (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, client_entity_id, id),
            FOREIGN KEY (tenant_id, client_entity_id, prior_snapshot_id)
                REFERENCES ledger_snapshots (tenant_id, client_entity_id, id)
        )
        """
    )
    tenant_table(op, "trial_balance_versions")
    op.execute("REVOKE UPDATE, DELETE ON trial_balance_versions FROM abacus_app")
    insert_columns(
        op,
        "trial_balance_versions",
        (
            "tenant_id",
            "trial_balance_id",
            "client_entity_id",
            "version_no",
            "snapshot_id",
            "prior_snapshot_id",
            "adopted_by",
            "actor_kind",
            "reason",
            "content_fingerprint",
        ),
    )
    op.execute(
        """
        CREATE TABLE trial_balance_annotations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            trial_balance_id uuid NOT NULL,
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 64),
            area text NULL CHECK (length(area) BETWEEN 1 AND 120),
            wp_ref text NULL CHECK (wp_ref ~ '^[A-Z0-9][A-Z0-9.-]{0,19}$'),
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 500),
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, trial_balance_id) REFERENCES trial_balances (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX trial_balance_annotations_newest ON trial_balance_annotations "
        "(tenant_id, trial_balance_id, account_code, created_at DESC)"
    )
    tenant_table(op, "trial_balance_annotations")
    op.execute("REVOKE UPDATE, DELETE ON trial_balance_annotations FROM abacus_app")
    insert_columns(
        op,
        "trial_balance_annotations",
        ("tenant_id", "trial_balance_id", "account_code", "area", "wp_ref", "reason", "set_by"),
    )


def downgrade() -> None:
    for table in ("trial_balance_annotations", "trial_balance_versions", "trial_balances"):
        op.execute(f"DROP TABLE {table}")
