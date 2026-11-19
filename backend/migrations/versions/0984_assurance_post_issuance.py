"""Q-05-T12 (TASK-8718; DEC-5714; SPEC-711 AC-15 to AC-18): post-issuance cases, expand-only and
dark behind `audit.post_issuance`.

- `post_issuance_events`: one case per subsequently discovered fact on a released engagement
  (`PI-01`), its type, standard, source and status (status moves forward only by the service).
- `post_issuance_comparisons` (insert-only): each certified line beside its corrected amount.
- `post_issuance_evaluations` (insert-only): the total difference against the materiality frozen
  at release (clearly trivial, overall, share), with that materiality version.

Revision ID: 0984
Revises: 0983
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0984"
down_revision = "0983"
branch_labels = None
depends_on = None

TABLES = {
    "post_issuance_events": (
        """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            ref text NOT NULL CHECK (ref ~ '^PI-[0-9]{2,4}$'),
            type text NOT NULL CHECK (type IN ('subsequent_fact', 'omitted_procedure')),
            standard text NULL CHECK (standard IN ('au_c_560', 'au_c_585')),
            source_kind text NOT NULL CHECK (char_length(source_kind) BETWEEN 1 AND 40),
            received_at timestamptz NOT NULL,
            description_sealed bytea NOT NULL CHECK (octet_length(description_sealed) <= 65536),
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'analysing', 'awaiting_decision', 'decided')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, ref),
            UNIQUE (tenant_id, id)""",
        ("tenant_id", "engagement_id", "work_item_id", "ref", "type", "standard", "source_kind",
         "received_at", "description_sealed", "created_by"),
        False,
    ),
    "post_issuance_comparisons": (
        """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            event_id uuid NOT NULL,
            line_key text NOT NULL CHECK (char_length(line_key) BETWEEN 1 AND 40),
            as_certified numeric(20, 2) NOT NULL,
            as_corrected numeric(20, 2) NOT NULL,
            difference numeric(20, 2) NOT NULL,
            CHECK (difference = as_corrected - as_certified),
            UNIQUE (event_id, line_key),
            FOREIGN KEY (tenant_id, event_id) REFERENCES post_issuance_events (tenant_id, id)""",
        ("tenant_id", "event_id", "line_key", "as_certified", "as_corrected", "difference"),
        True,
    ),
    "post_issuance_evaluations": (
        """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            event_id uuid NOT NULL UNIQUE,
            total_difference numeric(20, 2) NOT NULL,
            clearly_trivial numeric(20, 2) NOT NULL CHECK (clearly_trivial >= 0),
            overall_materiality numeric(20, 2) NOT NULL CHECK (overall_materiality > 0),
            share_pct numeric(7, 1) NOT NULL,
            below_clearly_trivial boolean NOT NULL,
            disclosure_affected boolean NOT NULL DEFAULT false,
            materiality_version_id uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, event_id) REFERENCES post_issuance_events (tenant_id, id)""",
        ("tenant_id", "event_id", "total_difference", "clearly_trivial", "overall_materiality",
         "share_pct", "below_clearly_trivial", "disclosure_affected", "materiality_version_id"),
        True,
    ),
}  # fmt: skip


def upgrade() -> None:
    for table, (body, columns, immutable) in TABLES.items():
        op.execute(f"CREATE TABLE {table} ({body}\n        )")
        tenant_table(op, table)
        insert_columns(op, table, columns)
        if immutable:
            insert_only(op, table)
    op.execute("REVOKE UPDATE, DELETE ON post_issuance_events FROM abacus_app")
    op.execute("GRANT UPDATE (status) ON post_issuance_events TO abacus_app")


def downgrade() -> None:
    for table in reversed(list(TABLES)):
        op.execute(f"DROP TABLE {table}")
