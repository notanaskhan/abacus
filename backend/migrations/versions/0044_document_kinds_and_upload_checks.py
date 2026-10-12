"""Document kinds and upload checks (SPEC-029; TASK-055).

- `request_items.document_kind` (`bank_statement`, `ar_aging`, `ap_aging`, `schedule`) and
  `document_kind_source` (`rule`, `override`): which document a request expects, set by fixed
  keyword rules or by the team. Existing items are classified by the same rules here once.
- `upload_checks`: one row per mechanical check or ledger cross-check of an evidence version, by
  checker version, with its audience (`client` or `firm`) and code-computed values only.
  Insert-only.

Revision ID: 0044
Revises: 0043
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_KINDS = "('bank_statement', 'ar_aging', 'ap_aging', 'schedule')"
# The rules in `requests.classification.KIND_RULES`, first match wins, for existing items only.
_BACKFILL = (
    ("bank_statement", r"\mbank statements?\M"),
    ("ar_aging", r"\m(aged (receivables|debtors)|AR aging|receivables aging)\M"),
    ("ap_aging", r"\m(aged (payables|creditors)|AP aging|payables aging)\M"),
    ("schedule", r"\m(schedules?|reconciliations?|roll-?forwards?)\M"),
)
_CHECKS_INSERT = (
    "tenant_id",
    "engagement_id",
    "evidence_version_id",
    "checker_version",
    "document_kind",
    "check_code",
    "outcome",
    "audience",
    "reason",
    "expected_date",
    "found_date",
    "amount",
    "difference",
    "account_code",
    "ref_item_id",
)


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE request_items "
        f"ADD COLUMN document_kind text NULL CHECK (document_kind IN {_KINDS}), "
        "ADD COLUMN document_kind_source text NULL "
        "CHECK (document_kind_source IN ('rule', 'override')), "
        "ADD CONSTRAINT request_items_kind_has_source "
        "CHECK (document_kind IS NULL OR document_kind_source IS NOT NULL)"
    )
    op.execute("ALTER TABLE request_items NO FORCE ROW LEVEL SECURITY")
    for kind, pattern in _BACKFILL:
        op.execute(
            sa.text(
                "UPDATE request_items SET document_kind = :kind, document_kind_source = 'rule' "
                "WHERE document_kind IS NULL AND (description || ' ' || audit_area) ~* :pattern"
            ).bindparams(kind=kind, pattern=pattern)
        )
    op.execute("ALTER TABLE request_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "GRANT INSERT (document_kind, document_kind_source), "
        "UPDATE (document_kind, document_kind_source) ON request_items TO abacus_app"
    )
    op.execute(
        f"""
        CREATE TABLE upload_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            checker_version text NOT NULL CHECK (checker_version ~ '^v[0-9]{{1,4}}$'),
            document_kind text NULL CHECK (document_kind IN {_KINDS}),
            check_code text NOT NULL CHECK (check_code ~ '^[a-z][a-z_]{{0,39}}$'),
            outcome text NOT NULL CHECK (outcome IN ('passed', 'problem', 'not_applicable')),
            audience text NOT NULL CHECK (audience IN ('client', 'firm')),
            reason text NULL CHECK (reason ~ '^[a-z][a-z_]{{0,39}}$'),
            expected_date date NULL,
            found_date date NULL,
            amount numeric(20, 2) NULL,
            difference numeric(20, 2) NULL,
            account_code text NULL CHECK (length(account_code) BETWEEN 1 AND 40),
            ref_item_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE NULLS NOT DISTINCT
                (tenant_id, evidence_version_id, checker_version, document_kind, check_code),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "upload_checks")
    op.execute("REVOKE UPDATE, DELETE ON upload_checks FROM abacus_app")
    insert_columns(op, "upload_checks", _CHECKS_INSERT)


def downgrade() -> None:
    op.execute("DROP TABLE upload_checks")
    op.execute(
        "REVOKE INSERT (document_kind, document_kind_source), "
        "UPDATE (document_kind, document_kind_source) ON request_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE request_items DROP CONSTRAINT request_items_kind_has_source, "
        "DROP COLUMN document_kind, DROP COLUMN document_kind_source"
    )
