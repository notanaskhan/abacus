"""Fieldwork, part 1a (SPEC-037; TASK-083; ADR-131, ADR-132).

- `engagement_materiality` (insert-only; the newest is current): overall, performance and trivial,
  with the benchmark and percentage as text, set by a person (Q3).
- `fieldwork_settings` (insert-only per firm; the newest is current): the firm's default criteria.
- `procedures`: one journal entry testing per engagement (definition and version), its parameters
  and status; the app may update only its parameters and status.
- `populations`, `selections`, `selected_items` (insert-only): what code built and selected, so a
  selection can be re-performed (ADR-132).

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

_TABLES = (
    "selected_items",
    "selections",
    "populations",
    "procedures",
    "fieldwork_settings",
    "engagement_materiality",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engagement_materiality (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            overall numeric(18, 2) NOT NULL CHECK (overall > 0),
            performance numeric(18, 2) NOT NULL CHECK (performance > 0),
            trivial numeric(18, 2) NOT NULL CHECK (trivial > 0),
            benchmark text NOT NULL CHECK (length(benchmark) BETWEEN 1 AND 200),
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (trivial <= performance AND performance <= overall),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE fieldwork_settings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            settings jsonb NOT NULL,
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            definition text NOT NULL CHECK (definition IN ('journal_entry_testing')),
            definition_version integer NOT NULL CHECK (definition_version >= 1),
            parameters jsonb NOT NULL,
            status text NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'selecting', 'selected', 'failed')),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,49}$'),
            started_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT procedures_once UNIQUE (tenant_id, engagement_id, definition),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE populations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            gl_snapshot_id uuid NOT NULL,
            rule_version integer NOT NULL,
            entry_count integer NOT NULL CHECK (entry_count >= 0),
            line_count integer NOT NULL CHECK (line_count >= 0),
            total_debit numeric(20, 2) NOT NULL,
            total_credit numeric(20, 2) NOT NULL,
            tied boolean NOT NULL,
            failure text NULL CHECK (failure ~ '^[a-z][a-z_]{0,49}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (tied = (failure IS NULL)),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, gl_snapshot_id) REFERENCES gl_snapshots (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE selections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            population_id uuid NOT NULL,
            parameters jsonb NOT NULL,
            criteria_version integer NOT NULL,
            random_method text NOT NULL,
            seed bigint NOT NULL,
            item_count integer NOT NULL CHECK (item_count >= 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, population_id) REFERENCES populations (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX selections_newest ON selections (tenant_id, procedure_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE selected_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            selection_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            posted_on date NOT NULL,
            kind text NOT NULL,
            reference text NOT NULL,
            counterparty text NOT NULL,
            line_nos integer[] NOT NULL,
            accounts text[] NOT NULL,
            amount numeric(20, 2) NOT NULL,
            descriptions text[] NOT NULL,
            rules text[] NOT NULL CHECK (cardinality(rules) >= 1),
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 500),
            UNIQUE (tenant_id, selection_id, position),
            FOREIGN KEY (tenant_id, selection_id) REFERENCES selections (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "engagement_materiality",
        ("tenant_id", "engagement_id", "overall", "performance", "trivial", "benchmark", "set_by"),
    )
    insert_columns(op, "fieldwork_settings", ("tenant_id", "settings", "set_by"))
    insert_columns(
        op,
        "procedures",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "definition",
            "definition_version",
            "parameters",
            "started_by",
        ),
    )
    op.execute("GRANT UPDATE (parameters, status, failure_code) ON procedures TO abacus_app")
    insert_columns(
        op,
        "populations",
        (
            "id",
            "tenant_id",
            "procedure_id",
            "gl_snapshot_id",
            "rule_version",
            "entry_count",
            "line_count",
            "total_debit",
            "total_credit",
            "tied",
            "failure",
        ),
    )
    insert_columns(
        op,
        "selections",
        (
            "id",
            "tenant_id",
            "procedure_id",
            "population_id",
            "parameters",
            "criteria_version",
            "random_method",
            "seed",
            "item_count",
            "created_by",
        ),
    )
    insert_columns(
        op,
        "selected_items",
        (
            "tenant_id",
            "selection_id",
            "position",
            "posted_on",
            "kind",
            "reference",
            "counterparty",
            "line_nos",
            "accounts",
            "amount",
            "descriptions",
            "rules",
            "reason",
        ),
    )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
