"""Completion, release and archive, first slice (SPEC-314; TASK-332; A-07, record mode).

All insert-only, all human-only (CHECK):
- `eqr_concurrences`: the engagement quality reviewer concurs over a code-built digest
  (its SHA-256), attesting they weren't involved in performing the engagement.
- `completion_records`: the going-concern decision, the audit report record (opinion form,
  report date and the report document, an evidence version), the partner's approval of a report
  record, and the signed representation letter (document and date). The newest of each counts.
- `releases`: one per engagement (G8): the report released and its date, the gate facts as they
  stood, and the documentation completion date (60 days later).
- `archives`: one per engagement (G9): the seal (a SHA-256 Merkle root over every content hash
  the binder holds) and its manifest.

Revision ID: 0077
Revises: 0076
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def _insert_only(table: str, columns: tuple[str, ...]) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(op, table, columns)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE eqr_concurrences (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            digest_hash text NOT NULL CHECK (digest_hash ~ '^[0-9a-f]{64}$'),
            not_involved boolean NOT NULL CHECK (not_involved),
            concurred_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    _insert_only(
        "eqr_concurrences",
        (
            "tenant_id",
            "engagement_id",
            "digest_hash",
            "not_involved",
            "concurred_by",
            "actor_kind",
        ),
    )
    op.execute(
        """
        CREATE TABLE completion_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            kind text NOT NULL
                CHECK (kind IN ('going_concern', 'report', 'report_approval', 'rep_letter')),
            choice text NULL,
            emphasis boolean NULL,
            document_date date NULL,
            evidence_version_id uuid NULL,
            report_record_id uuid NULL,
            rationale text NULL CHECK (length(rationale) BETWEEN 1 AND 1000),
            recorded_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (kind <> 'going_concern' OR choice IN
                ('no_substantial_doubt', 'doubt_alleviated', 'doubt_exists')),
            CHECK (kind <> 'report' OR (choice IN ('unmodified', 'qualified', 'adverse',
                'disclaimer') AND document_date IS NOT NULL AND evidence_version_id IS NOT NULL)),
            CHECK (kind <> 'report_approval' OR report_record_id IS NOT NULL),
            CHECK (kind <> 'rep_letter' OR
                (document_date IS NOT NULL AND evidence_version_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, report_record_id) REFERENCES completion_records (tenant_id, id)
        )
        """
    )
    _insert_only(
        "completion_records",
        (
            "tenant_id",
            "engagement_id",
            "kind",
            "choice",
            "emphasis",
            "document_date",
            "evidence_version_id",
            "report_record_id",
            "rationale",
            "recorded_by",
            "actor_kind",
        ),
    )
    op.execute(
        """
        CREATE TABLE releases (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            report_record_id uuid NOT NULL,
            report_date date NOT NULL,
            documentation_due date NOT NULL,
            gates jsonb NOT NULL,
            released_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, engagement_id),
            CHECK (documentation_due > report_date),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, report_record_id) REFERENCES completion_records (tenant_id, id)
        )
        """
    )
    _insert_only(
        "releases",
        (
            "tenant_id",
            "engagement_id",
            "report_record_id",
            "report_date",
            "documentation_due",
            "gates",
            "released_by",
            "actor_kind",
        ),
    )
    op.execute(
        """
        CREATE TABLE archives (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            seal text NOT NULL CHECK (seal ~ '^[0-9a-f]{64}$'),
            leaf_count integer NOT NULL CHECK (leaf_count > 0),
            manifest jsonb NOT NULL,
            locked_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    _insert_only(
        "archives",
        (
            "tenant_id",
            "engagement_id",
            "seal",
            "leaf_count",
            "manifest",
            "locked_by",
            "actor_kind",
        ),
    )


def downgrade() -> None:
    for table in ("archives", "releases", "completion_records", "eqr_concurrences"):
        op.execute(f"DROP TABLE {table}")
