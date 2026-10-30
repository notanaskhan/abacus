"""Report templates as database content (P-11-T06; P-11 §4.2 "Migration 2"; ADR-320; SPEC-520
AC-1 to AC-5; P-38 expand-only).

Three tables in `methodology`, every one tenant-scoped with forced RLS. Firm content: rows arrive
only through `POST /v1/report-templates/import` (or the scenario loader's service call on the
synthetic tenant), never from a migration, a constant or the seed.

- `report_templates`: one per firm, family (the generated-document kind) and name.
- `report_template_versions` (insert-only): the DocBlock body, clause library, declared variables
  and synthetic sample data as imported, with the canonical `content_sha256` and the person who
  imported it. A correction is a new version.
- `report_template_publications` (insert-only): `published` or `deprecated`, always by a person
  (`by_user_id NOT NULL`) with the instant of their fresh second factor. The current version is
  the latest `published` row not followed by a `deprecated` row for that version; republishing an
  older version rolls back without a deploy.

Insert-only means `REVOKE UPDATE, DELETE` plus a trigger that refuses UPDATE, DELETE and TRUNCATE
for every role (ADR-004). Classification (ADR-031): bodies, clauses and variable declarations are
Internal firm content; sample data is synthetic by rule (Internal).

Revision ID: 0460
Revises: 0430
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0460"
down_revision = "0430"
branch_labels = None
depends_on = None

_FAMILIES = (
    "engagement_letter",
    "consent_7216",
    "representation_letter",
    "governance_letter",
    "audit_report",
    "review_report",
    "compilation_report",
    "notice_response",
    "delivery_cover_letter",
    "k1_cover_letter",
    "fs_package",
    "run_trace_export",
)
_LAYOUTS = ("letter", "consent_7216", "report", "notice_response", "package", "run_export")
_INSERT_ONLY = ("report_template_versions", "report_template_publications")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _immutable(table: str) -> None:
    insert_only(op, table)
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION report_template_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION report_template_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION report_template_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )

    op.execute(
        f"""
        CREATE TABLE report_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            family text NOT NULL CHECK (family IN ({_in(_FAMILIES)})),
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
            description text NOT NULL DEFAULT '' CHECK (char_length(description) <= 2000),
            created_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, family, name)
        )
        """
    )
    tenant_table(op, "report_templates")
    insert_columns(
        op,
        "report_templates",
        ("id", "tenant_id", "family", "name", "description", "created_by_user_id"),
    )
    # A template's identity never moves; its wording lives in versions.
    op.execute("REVOKE UPDATE, DELETE ON report_templates FROM abacus_app")

    op.execute(
        f"""
        CREATE TABLE report_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            layout_key text NOT NULL CHECK (layout_key IN ({_in(_LAYOUTS)})),
            body jsonb NOT NULL CHECK (jsonb_typeof(body) = 'array'),
            clauses jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(clauses) = 'array'),
            variables jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(variables) = 'array'),
            sample_data jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(sample_data) = 'object'),
            source text NOT NULL CHECK (source IN ('import', 'scenario_loader')),
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{{64}}$'),
            imported_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_id, version_no),
            -- 512 KB of body, clauses and variables together (AC-1 `too_large`).
            CHECK (
                pg_column_size(body) + pg_column_size(clauses) + pg_column_size(variables)
                <= 524288
            ),
            FOREIGN KEY (tenant_id, template_id) REFERENCES report_templates (tenant_id, id)
        )
        """
    )
    tenant_table(op, "report_template_versions")
    insert_columns(
        op,
        "report_template_versions",
        (
            "id",
            "tenant_id",
            "template_id",
            "version_no",
            "layout_key",
            "body",
            "clauses",
            "variables",
            "sample_data",
            "source",
            "content_sha256",
            "imported_by_user_id",
        ),
    )

    op.execute(
        """
        CREATE TABLE report_template_publications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            action text NOT NULL CHECK (action IN ('published', 'deprecated')),
            by_user_id uuid NOT NULL,
            mfa_at timestamptz NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- A publication names the person and when they last proved a second factor.
            CHECK (action <> 'published' OR mfa_at IS NOT NULL),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES report_template_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX report_template_publications_by_version "
        "ON report_template_publications (tenant_id, version_id, at)"
    )
    tenant_table(op, "report_template_publications")
    insert_columns(
        op,
        "report_template_publications",
        ("id", "tenant_id", "version_id", "action", "by_user_id", "mfa_at"),
    )

    for table in _INSERT_ONLY:
        _immutable(table)


def downgrade() -> None:
    for table in ("report_template_publications", "report_template_versions", "report_templates"):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION report_template_rows_immutable()")
