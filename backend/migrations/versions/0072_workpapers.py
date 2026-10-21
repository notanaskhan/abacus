"""Working papers and sign-offs, first slice (SPEC-308; TASK-319).

- Fieldwork's per-procedure tables are renamed `procedure_workpaper_versions` and
  `procedure_workpaper_signatures`, so the glossary's `workpaper_*` names belong to the
  workpapers module (DEC-110: fieldwork moves onto the review grammar later).
- `workpapers` (insert-only): a working paper on an engagement's work item, coded per engagement
  ("C-100"), with its audit area.
- `workpaper_sections` (insert-only): its sections.
- `workpaper_cells` (insert-only): every value a cell has held; the newest counts. A cell key
  ("B4") on a sheet is a stable citation target ("C-100!B4").
- `workpaper_cell_citations` (insert-only): a cell's sources (an evidence version and where).
- `workpaper_versions` (insert-only): a content snapshot with its SHA-256, taken at each sign-off.
- `sign_offs` (insert-only, review module; the P-04 review grammar's first table): L1 preparer to
  L5 EQR on any registered reviewable, with the content hash signed; staleness is computed.

Revision ID: 0072
Revises: 0071
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def _insert_only(table: str, columns: tuple[str, ...]) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    insert_columns(op, table, columns)


def upgrade() -> None:
    op.execute("ALTER TABLE workpaper_signatures RENAME TO procedure_workpaper_signatures")
    op.execute("ALTER TABLE workpaper_versions RENAME TO procedure_workpaper_versions")
    op.execute(
        """
        CREATE TABLE workpapers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            code text NOT NULL CHECK (code ~ '^[A-Z0-9][A-Z0-9.-]{0,19}$'),
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            audit_area text NULL CHECK (length(audit_area) BETWEEN 1 AND 120),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, code),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    _insert_only(
        "workpapers",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "code",
            "title",
            "audit_area",
            "created_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE workpaper_sections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            sheet_key text NOT NULL CHECK (sheet_key ~ '^[a-z][a-z0-9_]{0,39}$'),
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
            position integer NOT NULL CHECK (position >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, workpaper_id, sheet_key),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id)
        )
        """
    )
    _insert_only(
        "workpaper_sections", ("tenant_id", "workpaper_id", "sheet_key", "title", "position")
    )
    op.execute(
        """
        CREATE TABLE workpaper_cells (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            sheet_key text NOT NULL DEFAULT 'main',
            cell_key text NOT NULL CHECK (cell_key ~ '^[A-Z]{1,2}[1-9][0-9]{0,3}$'),
            raw text NULL CHECK (length(raw) <= 2000),
            value_source text NOT NULL DEFAULT 'human'
                CHECK (value_source IN
                    ('human', 'formula', 'agent', 'tb_linked', 'engine_import')),
            tickmarks text[] NOT NULL DEFAULT '{}',
            set_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX workpaper_cells_newest "
        "ON workpaper_cells (tenant_id, workpaper_id, sheet_key, cell_key, created_at DESC)"
    )
    _insert_only(
        "workpaper_cells",
        (
            "tenant_id",
            "workpaper_id",
            "sheet_key",
            "cell_key",
            "raw",
            "value_source",
            "tickmarks",
            "set_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE workpaper_cell_citations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            sheet_key text NOT NULL DEFAULT 'main',
            cell_key text NOT NULL CHECK (cell_key ~ '^[A-Z]{1,2}[1-9][0-9]{0,3}$'),
            evidence_version_id uuid NOT NULL,
            locator text NULL CHECK (length(locator) BETWEEN 1 AND 120),
            added_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    _insert_only(
        "workpaper_cell_citations",
        (
            "tenant_id",
            "workpaper_id",
            "sheet_key",
            "cell_key",
            "evidence_version_id",
            "locator",
            "added_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE workpaper_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no > 0),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            content jsonb NOT NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, workpaper_id, version_no),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id)
        )
        """
    )
    _insert_only(
        "workpaper_versions",
        ("tenant_id", "workpaper_id", "version_no", "content_hash", "content", "created_by"),
    )
    op.execute(
        """
        CREATE TABLE sign_offs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            target_type text NOT NULL CHECK (target_type ~ '^[a-z][a-z_]{0,39}$'),
            target_id uuid NOT NULL,
            level smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            signed_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX sign_offs_by_target ON sign_offs (tenant_id, target_type, target_id, level)"
    )
    _insert_only(
        "sign_offs",
        (
            "tenant_id",
            "engagement_id",
            "target_type",
            "target_id",
            "level",
            "content_hash",
            "signed_by",
        ),
    )


def downgrade() -> None:
    for table in (
        "sign_offs",
        "workpaper_versions",
        "workpaper_cell_citations",
        "workpaper_cells",
        "workpaper_sections",
        "workpapers",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE procedure_workpaper_versions RENAME TO workpaper_versions")
    op.execute("ALTER TABLE procedure_workpaper_signatures RENAME TO workpaper_signatures")
