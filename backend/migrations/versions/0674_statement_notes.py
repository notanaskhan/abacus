"""A-06-T25 (DEC-2389): the statements' note templates and each version's notes, expand-only.

`methodology` (firm content): `statement_note_templates` and their versions (notes as JSON,
published by a person). No note wording is inserted here (AGENTS 16). `reporting`:
`statement_notes`, the notes a draft rendered from a published version, insert-only like the rest
of a statement version. And the app may now set a statement document's checklist version, which a
person picks (DEC-2390).

Revision ID: 0674
Revises: 0673
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0674"
down_revision = "0673"
branch_labels = None
depends_on = None

_TABLES = ("statement_note_templates", "statement_note_template_versions", "statement_notes")
INSERTS: dict[str, tuple[str, ...]] = {
    "statement_note_templates": ("tenant_id", "framework_key", "name", "created_by"),
    "statement_note_template_versions": (
        "tenant_id",
        "template_id",
        "version",
        "notes",
        "source_file_sha256",
        "imported_by",
    ),
    "statement_notes": (
        "tenant_id",
        "statement_version_id",
        "template_version_id",
        "number",
        "title",
        "body",
        "unresolved",
    ),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "statement_note_template_versions": ("status", "published_by", "published_at"),
}


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE statement_note_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            framework_key text NOT NULL CHECK (framework_key ~ '^[a-z][a-z0-9_]{1,39}$'),
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, framework_key, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE statement_note_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            notes jsonb NOT NULL CHECK (jsonb_typeof(notes) = 'array'),
            source_file_sha256 text NOT NULL CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            published_by uuid NULL,
            published_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_id, version),
            CHECK ((status = 'published')
                = (published_by IS NOT NULL AND published_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, template_id)
                REFERENCES statement_note_templates (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE statement_notes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            statement_version_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            number integer NOT NULL CHECK (number BETWEEN 1 AND 999),
            title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
            body text NOT NULL CHECK (char_length(body) <= 20000),
            unresolved text[] NOT NULL DEFAULT '{}' CHECK (cardinality(unresolved) <= 100),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, statement_version_id, number),
            FOREIGN KEY (tenant_id, statement_version_id)
                REFERENCES statement_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES statement_note_template_versions (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    insert_only(op, "statement_notes")
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute("REVOKE UPDATE ON statement_note_templates FROM abacus_app")
    # DEC-2390: a person picks a document's checklist; nothing could set this column before.
    op.execute("GRANT UPDATE (checklist_template_version_id) ON statement_documents TO abacus_app")
    op.execute(
        "CREATE TRIGGER statement_notes_immutable BEFORE UPDATE OR DELETE ON statement_notes "
        "FOR EACH ROW EXECUTE FUNCTION statement_rows_immutable()"
    )
    op.execute(
        "CREATE TRIGGER statement_notes_no_truncate BEFORE TRUNCATE ON statement_notes "
        "FOR EACH STATEMENT EXECUTE FUNCTION statement_rows_immutable()"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (checklist_template_version_id) ON statement_documents FROM abacus_app"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
