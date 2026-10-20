"""Completion: deficiency severity, proposed adjusting entries and the representation list
(SPEC-301; TASK-302).

- `finding_severities` (insert-only): a severity proposed on a finding, or concluded by the
  engagement partner; the newest of each stage counts.
- `finding_communications` (insert-only): a concluded deficiency communicated, when and to whom.
- `adjustments` (insert-only): a proposed entry, AJE-n or RJE-n per engagement.
- `adjustment_lines` (insert-only): its lines; code checks debits equal credits.
- `adjustment_events` (insert-only): approved; the client accepted or declined (passed).
- `representations` (insert-only): a specific representation for the letter.
- `representation_removals` (insert-only): one taken off the list.

Revision ID: 0067
Revises: 0066
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

_SEVERITY = "('deficiency', 'significant_deficiency', 'material_weakness')"


def _insert_only(table: str, columns: tuple[str, ...]) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(op, table, columns)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE finding_severities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            finding_id uuid NOT NULL,
            stage text NOT NULL CHECK (stage IN ('proposed', 'concluded')),
            severity text NOT NULL CHECK (severity IN {_SEVERITY}),
            rationale text NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id),
            CHECK (stage = 'proposed' OR rationale IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX finding_severities_by_finding "
        "ON finding_severities (tenant_id, finding_id, created_at DESC)"
    )
    _insert_only(
        "finding_severities",
        ("tenant_id", "finding_id", "stage", "severity", "rationale", "set_by"),
    )
    op.execute(
        """
        CREATE TABLE finding_communications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            finding_id uuid NOT NULL,
            communicated_on date NOT NULL,
            recipients text NOT NULL CHECK (length(recipients) BETWEEN 1 AND 300),
            recorded_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id)
        )
        """
    )
    _insert_only(
        "finding_communications",
        ("tenant_id", "finding_id", "communicated_on", "recipients", "recorded_by"),
    )
    op.execute(
        """
        CREATE TABLE adjustments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('aje', 'rje')),
            number integer NOT NULL CHECK (number > 0),
            finding_id uuid NULL,
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 500),
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, kind, number),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id)
        )
        """
    )
    _insert_only(
        "adjustments",
        ("tenant_id", "engagement_id", "kind", "number", "finding_id", "description", "raised_by"),
    )
    op.execute(
        """
        CREATE TABLE adjustment_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            adjustment_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 64),
            debit numeric(18, 2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
            credit numeric(18, 2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
            UNIQUE (tenant_id, adjustment_id, position),
            FOREIGN KEY (tenant_id, adjustment_id) REFERENCES adjustments (tenant_id, id),
            CHECK ((debit = 0) <> (credit = 0))
        )
        """
    )
    _insert_only(
        "adjustment_lines",
        ("tenant_id", "adjustment_id", "position", "account_code", "debit", "credit"),
    )
    op.execute(
        """
        CREATE TABLE adjustment_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            adjustment_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('approved', 'client_accepted', 'client_declined')),
            note text NULL CHECK (length(note) BETWEEN 1 AND 1000),
            by_user uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, adjustment_id, kind),
            FOREIGN KEY (tenant_id, adjustment_id) REFERENCES adjustments (tenant_id, id)
        )
        """
    )
    _insert_only("adjustment_events", ("tenant_id", "adjustment_id", "kind", "note", "by_user"))
    op.execute(
        """
        CREATE TABLE representations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            body text NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
            finding_id uuid NULL,
            adjustment_id uuid NULL,
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, finding_id) REFERENCES findings (tenant_id, id),
            FOREIGN KEY (tenant_id, adjustment_id) REFERENCES adjustments (tenant_id, id)
        )
        """
    )
    _insert_only(
        "representations",
        ("tenant_id", "engagement_id", "body", "finding_id", "adjustment_id", "raised_by"),
    )
    op.execute(
        """
        CREATE TABLE representation_removals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            representation_id uuid NOT NULL,
            removed_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, representation_id),
            FOREIGN KEY (tenant_id, representation_id) REFERENCES representations (tenant_id, id)
        )
        """
    )
    _insert_only("representation_removals", ("tenant_id", "representation_id", "removed_by"))


def downgrade() -> None:
    for table in (
        "representation_removals",
        "representations",
        "adjustment_events",
        "adjustment_lines",
        "adjustments",
        "finding_communications",
        "finding_severities",
    ):
        op.execute(f"DROP TABLE {table}")
