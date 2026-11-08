"""A-07-T22 (TASK-6206; DEC-2806): the firm's assurance checklist templates, as content.

A-07-T12 (DEC-2315) left the completion, EQR and archive checklists in the synthetic seed's content
file because nothing could import them. They are firm content (AGENTS 16), so they get a home here,
owned by `methodology` beside the disclosure-checklist templates (0660):

- `assurance_checklist_templates`: one per (kind, engagement type, name). `kind` is `completion`
  (AUD-19's checklist), `eqr` (AUD-18's) or `archive` (AUD-25's).
- `assurance_checklist_template_versions` (insert-only items, status moves draft → published by a
  person with fresh MFA): the items as JSON (`key`, `text`, and for completion items the gate tag,
  whether it depends on the client, when it falls due and whether code derives it).

`completion_items.template_version_id` (0664) gets its foreign key here, NOT VALID then validated
(the table holds no rows before the projector runs).

Revision ID: 0741
Revises: 0740
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0741"
down_revision = "0740"
branch_labels = None
depends_on = None

_SHA = "~ '^[0-9a-f]{64}$'"
_TABLES = ("assurance_checklist_templates", "assurance_checklist_template_versions")
INSERTS = {
    "assurance_checklist_templates": (
        "tenant_id", "kind", "engagement_type", "name", "created_by",
    ),
    "assurance_checklist_template_versions": (
        "tenant_id", "template_id", "version", "items", "source_file_sha256", "imported_by",
    ),
}  # fmt: skip
UPDATES = {"assurance_checklist_template_versions": ("status", "published_by", "published_at")}
_IMMUTABLE_ITEMS = """
CREATE FUNCTION assurance_checklist_items_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'assurance checklist template versions are never deleted';
    END IF;
    IF NEW.items IS DISTINCT FROM OLD.items OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.template_id IS DISTINCT FROM OLD.template_id
       OR NEW.source_file_sha256 IS DISTINCT FROM OLD.source_file_sha256 THEN
        RAISE EXCEPTION 'a published checklist is a new version, never an edit';
    END IF;
    IF OLD.status = 'published' THEN
        RAISE EXCEPTION 'a published checklist version does not change';
    END IF;
    RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE assurance_checklist_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('completion', 'eqr', 'archive')),
            engagement_type text NOT NULL CHECK (engagement_type ~ '^[a-z][a-z0-9_]{1,39}$'),
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, kind, engagement_type, name)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE assurance_checklist_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            items jsonb NOT NULL CHECK (jsonb_typeof(items) = 'array'
                AND jsonb_array_length(items) BETWEEN 1 AND 60),
            source_file_sha256 text NOT NULL CHECK (source_file_sha256 {_SHA}),
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
                REFERENCES assurance_checklist_templates (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute(_IMMUTABLE_ITEMS)
    op.execute("REVOKE ALL ON FUNCTION assurance_checklist_items_frozen() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER assurance_checklist_template_versions_frozen BEFORE UPDATE OR DELETE "
        "ON assurance_checklist_template_versions "
        "FOR EACH ROW EXECUTE FUNCTION assurance_checklist_items_frozen()"
    )
    op.execute(
        "ALTER TABLE completion_items ADD CONSTRAINT completion_items_template_version_fk "
        "FOREIGN KEY (tenant_id, template_version_id) "
        "REFERENCES assurance_checklist_template_versions (tenant_id, id) NOT VALID"
    )
    op.execute(
        "ALTER TABLE completion_items VALIDATE CONSTRAINT completion_items_template_version_fk"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE completion_items DROP CONSTRAINT completion_items_template_version_fk")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION assurance_checklist_items_frozen()")
