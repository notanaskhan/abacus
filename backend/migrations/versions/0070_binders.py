"""Binders (F-03-T14; plan migration "0058_binders").

- `request_lists` become binders on a work item: `work_item_id` (backfilled from the engagement's
  assurance work item; filled the same way by a trigger when an insert leaves it out), `name`,
  `kind`, `part`, `status`, the published and marked-done stamps, `prior_year_source_ref`.
- One binder per (work item, kind, part) replaces one list per engagement (DEC-31: "pt 2").
- `request_categories`: a binder's sections, backfilled from the items' audit areas.

Existing lists read `published` (they're already in use); new binders start `draft` unless the
caller says otherwise (the publish flow arrives with BND-01).

Revision ID: 0070
Revises: 0069
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

_STAMPS = "status, published_at, published_by, marked_done_at, marked_done_by"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE request_lists
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN name text NULL CHECK (length(name) BETWEEN 1 AND 200),
            ADD COLUMN kind text NOT NULL DEFAULT 'pbc'
                CHECK (kind IN ('organizer', 'pbc', 'close_intake', 'intake', 'third_party')),
            ADD COLUMN part integer NOT NULL DEFAULT 1 CHECK (part BETWEEN 1 AND 20),
            ADD COLUMN status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'unpublished', 'complete', 'closed')),
            ADD COLUMN published_at timestamptz NULL,
            ADD COLUMN published_by uuid NULL,
            ADD COLUMN marked_done_at timestamptz NULL,
            ADD COLUMN marked_done_by uuid NULL,
            ADD COLUMN prior_year_source_ref uuid NULL
        """
    )
    tables = ("request_lists", "work_items", "request_items")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE request_lists l SET
            work_item_id = w.id,
            name = 'Requests',
            status = 'published',
            published_at = l.created_at
        FROM work_items w
        WHERE w.tenant_id = l.tenant_id AND w.engagement_id = l.engagement_id
          AND w.kind = 'assurance'
        """
    )
    op.execute(
        """
        CREATE TABLE request_categories (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            request_list_id uuid NOT NULL,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            position integer NOT NULL CHECK (position >= 0),
            UNIQUE (tenant_id, request_list_id, name),
            FOREIGN KEY (tenant_id, request_list_id) REFERENCES request_lists (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        INSERT INTO request_categories (tenant_id, request_list_id, name, position)
        SELECT tenant_id, request_list_id, audit_area,
               (row_number() OVER (PARTITION BY request_list_id ORDER BY first_seen)) - 1
        FROM (
            SELECT tenant_id, request_list_id, audit_area, min(created_at) AS first_seen
            FROM request_items GROUP BY tenant_id, request_list_id, audit_area
        ) areas
        """
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE request_lists ALTER COLUMN work_item_id SET NOT NULL, "
        "ALTER COLUMN name SET NOT NULL, ALTER COLUMN name SET DEFAULT 'Requests'"
    )
    op.execute(
        "ALTER TABLE request_lists ADD CONSTRAINT request_lists_work_item_fkey "
        "FOREIGN KEY (tenant_id, engagement_id, work_item_id) "
        "REFERENCES work_items (tenant_id, engagement_id, id)"
    )
    op.execute(
        "ALTER TABLE request_lists DROP CONSTRAINT request_lists_tenant_id_engagement_id_key"
    )
    op.execute(
        "ALTER TABLE request_lists ADD CONSTRAINT request_lists_binder_key "
        "UNIQUE (tenant_id, work_item_id, kind, part)"
    )
    # A binder inserted without its work item joins the engagement's assurance work item (else
    # its first): today's request paths and tooling keep working unchanged.
    op.execute(
        """
        CREATE FUNCTION request_list_work_item() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.work_item_id IS NULL THEN
                SELECT id INTO NEW.work_item_id FROM work_items
                WHERE tenant_id = NEW.tenant_id AND engagement_id = NEW.engagement_id
                ORDER BY (kind = 'assurance') DESC, created_at
                LIMIT 1;
                IF NEW.work_item_id IS NULL THEN
                    RAISE EXCEPTION 'foreign key: no work item for the engagement'
                        USING ERRCODE = 'foreign_key_violation';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER request_lists_work_item BEFORE INSERT ON request_lists "
        "FOR EACH ROW EXECUTE FUNCTION request_list_work_item()"
    )
    op.execute(f"GRANT UPDATE ({_STAMPS}) ON request_lists TO abacus_app")
    insert_columns(
        op,
        "request_lists",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "name",
            "kind",
            "part",
            "status",
            "prior_year_source_ref",
        ),
    )
    tenant_table(op, "request_categories")
    op.execute("REVOKE UPDATE, DELETE ON request_categories FROM abacus_app")
    insert_columns(op, "request_categories", ("tenant_id", "request_list_id", "name", "position"))


def downgrade() -> None:
    op.execute("DROP TABLE request_categories")
    op.execute(f"REVOKE UPDATE ({_STAMPS}) ON request_lists FROM abacus_app")
    insert_columns(op, "request_lists", ("id", "tenant_id", "engagement_id"))
    op.execute("DROP TRIGGER request_lists_work_item ON request_lists")
    op.execute("DROP FUNCTION request_list_work_item()")
    op.execute("ALTER TABLE request_lists DROP CONSTRAINT request_lists_binder_key")
    op.execute(
        "ALTER TABLE request_lists ADD CONSTRAINT request_lists_tenant_id_engagement_id_key "
        "UNIQUE (tenant_id, engagement_id)"
    )
    op.execute("ALTER TABLE request_lists DROP CONSTRAINT request_lists_work_item_fkey")
    op.execute(
        "ALTER TABLE request_lists DROP COLUMN work_item_id, DROP COLUMN name, "
        "DROP COLUMN kind, DROP COLUMN part, DROP COLUMN status, DROP COLUMN published_at, "
        "DROP COLUMN published_by, DROP COLUMN marked_done_at, DROP COLUMN marked_done_by, "
        "DROP COLUMN prior_year_source_ref"
    )
