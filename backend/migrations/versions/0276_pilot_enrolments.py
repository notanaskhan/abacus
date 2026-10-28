"""Pilot enrolments and metric snapshots (Q-04-T007; Q-04 §4; DEC-716).

- `pilot_enrolments`: one work item's pilot, its window, its mode (`shadow` → `live` →
  `system_of_record`, or `exited`), the baseline days the firm agreed, and the named person who
  confirmed `system_of_record`: `CHECK (mode <> 'system_of_record' OR confirmed_by IS NOT NULL)`.
  One enrolment per work item. The app may change the mode, the confirming person and the time.
- `pilot_metric_snapshots`: insert-only computed metrics per enrolment, metric key, optional
  subject and period, `UNIQUE NULLS NOT DISTINCT`, so a NULL subject cannot be inserted twice.

Forced row-level security on both (tenant isolation). Written with the platform module.

Revision ID: 0276
Revises: 0275 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pilot_enrolments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            window_start date NOT NULL,
            window_end date NOT NULL,
            mode text NOT NULL DEFAULT 'shadow'
                CHECK (mode IN ('shadow', 'live', 'system_of_record', 'exited')),
            baseline_days integer NULL CHECK (baseline_days BETWEEN 0 AND 3650),
            confirmed_by uuid NULL,
            confirmed_at timestamptz NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT pilot_enrolments_one_per_work_item UNIQUE (tenant_id, work_item_id),
            CONSTRAINT pilot_enrolments_window CHECK (window_end >= window_start),
            CONSTRAINT pilot_enrolments_confirmed CHECK (
                mode <> 'system_of_record'
                OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE pilot_metric_snapshots (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            enrolment_id uuid NOT NULL,
            metric_key text NOT NULL CHECK (metric_key ~ '^[a-z][a-z0-9_.]{1,79}$'),
            subject_id uuid NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            value numeric(20, 4) NOT NULL,
            computed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT pilot_metric_snapshots_period CHECK (period_end >= period_start),
            CONSTRAINT pilot_metric_snapshots_once UNIQUE NULLS NOT DISTINCT
                (tenant_id, enrolment_id, metric_key, subject_id, period_start, period_end),
            FOREIGN KEY (tenant_id, enrolment_id) REFERENCES pilot_enrolments (tenant_id, id)
        )
        """
    )
    for table in ("pilot_enrolments", "pilot_metric_snapshots"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON pilot_enrolments FROM abacus_app")
    op.execute(
        "GRANT UPDATE (mode, confirmed_by, confirmed_at, updated_at) ON pilot_enrolments "
        "TO abacus_app"
    )
    insert_columns(
        op,
        "pilot_enrolments",
        ("tenant_id", "work_item_id", "window_start", "window_end", "baseline_days", "created_by"),
    )
    insert_only(op, "pilot_metric_snapshots")
    insert_columns(
        op,
        "pilot_metric_snapshots",
        (
            "tenant_id",
            "enrolment_id",
            "metric_key",
            "subject_id",
            "period_start",
            "period_end",
            "value",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE pilot_metric_snapshots")
    op.execute("DROP TABLE pilot_enrolments")
