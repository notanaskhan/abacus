"""Fieldwork, part 1b (SPEC-037; TASK-078; ADR-116).

All insert-only (the newest row is current where it matters):
- `item_results`: a person's result on a selected entry (`supported`, `exception` with a note,
  `not_tested` with a reason) and the evidence versions it relies on.
- `item_support_requests`: a request item created to ask the client for an entry's support.
- `procedure_conclusions`: the preparer's conclusion.
- `workpaper_versions`: what a signed version includes (selection, result and conclusion IDs) and
  the SHA-256 of its rendered bytes (D1: re-rendered and checked on download).
- `workpaper_signatures`: `ready` (preparer) or `reviewed` (another person), per version.

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

_TABLES = (
    "workpaper_signatures",
    "workpaper_versions",
    "procedure_conclusions",
    "item_support_requests",
    "item_results",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE selected_items ADD CONSTRAINT selected_items_by_id UNIQUE (tenant_id, id)"
    )
    op.execute(
        """
        CREATE TABLE item_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            selected_item_id uuid NOT NULL,
            result text NOT NULL CHECK (result IN ('supported', 'exception', 'not_tested')),
            note text NULL CHECK (length(note) BETWEEN 1 AND 2000),
            evidence_version_ids uuid[] NOT NULL DEFAULT '{}',
            recorded_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (result = 'supported' OR note IS NOT NULL),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX item_results_newest ON item_results "
        "(tenant_id, selected_item_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE item_support_requests (
            tenant_id uuid NOT NULL,
            selected_item_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            requested_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, selected_item_id, request_item_id),
            FOREIGN KEY (tenant_id, selected_item_id) REFERENCES selected_items (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE procedure_conclusions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
            written_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE workpaper_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            procedure_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            selection_id uuid NOT NULL,
            result_ids uuid[] NOT NULL,
            conclusion_id uuid NOT NULL,
            materiality_id uuid NOT NULL,
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, procedure_id, version),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, selection_id) REFERENCES selections (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE workpaper_signatures (
            tenant_id uuid NOT NULL,
            workpaper_version_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('ready', 'reviewed')),
            signed_by uuid NOT NULL,
            role text NOT NULL CHECK (length(role) BETWEEN 1 AND 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, workpaper_version_id, kind),
            FOREIGN KEY (tenant_id, workpaper_version_id)
                REFERENCES workpaper_versions (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "item_results",
        ("tenant_id", "selected_item_id", "result", "note", "evidence_version_ids", "recorded_by"),
    )
    insert_columns(
        op,
        "item_support_requests",
        ("tenant_id", "selected_item_id", "request_item_id", "requested_by"),
    )
    insert_columns(
        op, "procedure_conclusions", ("tenant_id", "procedure_id", "text", "written_by")
    )
    insert_columns(
        op,
        "workpaper_versions",
        (
            "id",
            "tenant_id",
            "procedure_id",
            "version",
            "selection_id",
            "result_ids",
            "conclusion_id",
            "materiality_id",
            "sha256",
        ),
    )
    insert_columns(
        op,
        "workpaper_signatures",
        ("tenant_id", "workpaper_version_id", "kind", "signed_by", "role"),
    )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE selected_items DROP CONSTRAINT selected_items_by_id")
