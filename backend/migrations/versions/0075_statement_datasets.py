"""Approved statement transactions (SPEC-312 phase 2-3; TASK-324).

- `statement_datasets` (insert-only): one approval per evidence version: the statement's
  period, balances (printed, or entered by the approver when the file doesn't print them), the
  reconciliation code computed, and who approved it. Only a human approves (CHECK), and only a
  reconciled statement (CHECK: opening + included lines = closing).
- `statement_transactions` (insert-only): each line as approved; an excluded line keeps its
  reason (CHECK).

Revision ID: 0075
Revises: 0074
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE statement_datasets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            format text NOT NULL CHECK (format IN ('pdf_text', 'csv', 'ofx')),
            account_kind text NOT NULL CHECK (account_kind IN ('credit_card', 'bank', 'unknown')),
            issuer text NULL CHECK (length(issuer) BETWEEN 1 AND 80),
            last4 text NULL CHECK (last4 ~ '^[0-9]{4}$'),
            period_start date NULL,
            period_end date NULL,
            opening numeric(18, 2) NOT NULL,
            closing numeric(18, 2) NOT NULL,
            opening_source text NOT NULL CHECK (opening_source IN ('printed', 'entered')),
            closing_source text NOT NULL CHECK (closing_source IN ('printed', 'entered')),
            included_total numeric(18, 2) NOT NULL,
            line_count integer NOT NULL CHECK (line_count > 0),
            excluded_count integer NOT NULL CHECK (excluded_count >= 0),
            signs_flipped boolean NOT NULL DEFAULT false,
            approved_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, evidence_version_id),
            CHECK (opening + included_total = closing),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "statement_datasets")
    op.execute("REVOKE UPDATE, DELETE ON statement_datasets FROM abacus_app")
    insert_columns(
        op,
        "statement_datasets",
        (
            "tenant_id",
            "engagement_id",
            "request_item_id",
            "evidence_version_id",
            "format",
            "account_kind",
            "issuer",
            "last4",
            "period_start",
            "period_end",
            "opening",
            "closing",
            "opening_source",
            "closing_source",
            "included_total",
            "line_count",
            "excluded_count",
            "signs_flipped",
            "approved_by",
            "actor_kind",
        ),
    )
    op.execute(
        """
        CREATE TABLE statement_transactions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            dataset_id uuid NOT NULL,
            position integer NOT NULL CHECK (position > 0),
            posted_on date NULL,
            description text NOT NULL CHECK (length(description) <= 200),
            amount numeric(18, 2) NOT NULL,
            page integer NULL CHECK (page > 0),
            excluded boolean NOT NULL DEFAULT false,
            exclusion_reason text NULL CHECK (length(exclusion_reason) BETWEEN 1 AND 200),
            UNIQUE (tenant_id, dataset_id, position),
            CHECK (excluded = (exclusion_reason IS NOT NULL)),
            FOREIGN KEY (tenant_id, dataset_id) REFERENCES statement_datasets (tenant_id, id)
        )
        """
    )
    tenant_table(op, "statement_transactions")
    op.execute("REVOKE UPDATE, DELETE ON statement_transactions FROM abacus_app")
    insert_columns(
        op,
        "statement_transactions",
        (
            "tenant_id",
            "dataset_id",
            "position",
            "posted_on",
            "description",
            "amount",
            "page",
            "excluded",
            "exclusion_reason",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE statement_transactions")
    op.execute("DROP TABLE statement_datasets")
