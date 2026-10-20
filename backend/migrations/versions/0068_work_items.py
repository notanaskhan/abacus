"""Work items (F-03-T05; plan migration "0056_work_items", renumbered on main).

- `work_items`: a unit of work inside an engagement (an audit, a return, a monthly close, a
  notice, an advisory project). One `assurance` work item per engagement at most.
- `assurance_work_items`: the assurance subtype (phase, auto mode, group audit).
- `work_item_assignments` (insert-only): who does what on a work item; removal is a new row.
- `engagement_entities` (insert-only): the entities an engagement covers; one `primary`.

Backfill: every engagement gets one assurance work item (phase `planning`, or `archived` for an
archived engagement) and one primary entity link. New engagements get both from the
`engagement_work_item_defaults` trigger, so every insert path keeps the invariant.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

_KINDS = "('assurance', 'tax_return', 'close', 'notice', 'advisory_project')"
_FUNCTIONS = (
    "('preparer', 'first_level_reviewer', 'detail_reviewer', 'manager_reviewer', 'signer', "
    "'eqr', 'close_preparer', 'close_reviewer', 'project_lead', 'specialist')"
)
_PHASES = (
    "('planning', 'fieldwork', 'in_review', 'completion', 'ready_to_release', 'released', "
    "'archiving', 'archived')"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE work_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_id uuid NOT NULL,
            client_entity_id uuid NULL,
            kind text NOT NULL CHECK (kind IN {_KINDS}),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            period_start date NULL,
            period_end date NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
            office_id uuid NULL,
            due_on date NULL,
            archived_at timestamptz NULL,
            archive_locked_at timestamptz NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX work_items_one_assurance ON work_items (tenant_id, engagement_id) "
        "WHERE kind = 'assurance'"
    )
    op.execute("CREATE INDEX work_items_by_engagement ON work_items (tenant_id, engagement_id)")
    tenant_table(op, "work_items")
    op.execute("REVOKE UPDATE, DELETE ON work_items FROM abacus_app")
    op.execute(
        "GRANT UPDATE (name, status, due_on, archived_at, archive_locked_at) "
        "ON work_items TO abacus_app"
    )
    insert_columns(
        op,
        "work_items",
        (
            "tenant_id",
            "engagement_id",
            "client_id",
            "client_entity_id",
            "kind",
            "name",
            "period_start",
            "period_end",
            "office_id",
            "due_on",
            "created_by",
        ),
    )
    op.execute(
        f"""
        CREATE TABLE assurance_work_items (
            work_item_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            assurance_type text NOT NULL CHECK (length(assurance_type) BETWEEN 1 AND 60),
            phase text NOT NULL DEFAULT 'planning' CHECK (phase IN {_PHASES}),
            standards_set_id uuid NULL,
            auto_mode boolean NOT NULL DEFAULT false,
            is_group_audit boolean NOT NULL DEFAULT false,
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    tenant_table(op, "assurance_work_items")
    op.execute("REVOKE UPDATE, DELETE ON assurance_work_items FROM abacus_app")
    op.execute("GRANT UPDATE (phase, auto_mode) ON assurance_work_items TO abacus_app")
    insert_columns(
        op,
        "assurance_work_items",
        (
            "work_item_id",
            "tenant_id",
            "engagement_id",
            "assurance_type",
            "phase",
            "is_group_audit",
        ),
    )
    op.execute(
        f"""
        CREATE TABLE work_item_assignments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            user_id uuid NOT NULL,
            function text NOT NULL CHECK (function IN {_FUNCTIONS}),
            assigned_by uuid NOT NULL,
            assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            removed_at timestamptz NULL,
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX work_item_assignments_by_item "
        "ON work_item_assignments (tenant_id, work_item_id, assigned_at DESC)"
    )
    tenant_table(op, "work_item_assignments")
    op.execute("REVOKE UPDATE, DELETE ON work_item_assignments FROM abacus_app")
    insert_columns(
        op,
        "work_item_assignments",
        (
            "tenant_id",
            "work_item_id",
            "engagement_id",
            "user_id",
            "function",
            "assigned_by",
            "removed_at",
        ),
    )
    op.execute(
        """
        CREATE TABLE engagement_entities (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            role text NOT NULL CHECK (role IN ('primary', 'component', 'household_member')),
            ownership_pct numeric(9, 6) NULL CHECK (ownership_pct > 0 AND ownership_pct <= 100),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, engagement_id, client_entity_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX engagement_entities_one_primary "
        "ON engagement_entities (tenant_id, engagement_id) WHERE role = 'primary'"
    )
    tenant_table(op, "engagement_entities")
    op.execute("REVOKE UPDATE, DELETE ON engagement_entities FROM abacus_app")
    insert_columns(
        op,
        "engagement_entities",
        ("tenant_id", "engagement_id", "client_entity_id", "role", "ownership_pct"),
    )
    # Every engagement holds its assurance work item and primary entity from the start: one
    # trigger keeps the invariant for every insert path (service, tooling, tests).
    op.execute(
        """
        CREATE FUNCTION engagement_work_item_defaults() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            item uuid;
        BEGIN
            INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind,
                                    name, period_start, period_end, created_by)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_id, NEW.client_entity_id, 'assurance',
                    NEW.name, NEW.fiscal_period_start, NEW.fiscal_period_end, NEW.created_by)
            RETURNING id INTO item;
            INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id,
                                              assurance_type)
            VALUES (item, NEW.tenant_id, NEW.id, NEW.type);
            INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role)
            VALUES (NEW.tenant_id, NEW.id, NEW.client_entity_id, 'primary');
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER engagements_work_item_defaults AFTER INSERT ON engagements "
        "FOR EACH ROW EXECUTE FUNCTION engagement_work_item_defaults()"
    )
    # Backfill as the owner, every firm at once (as 0036 does): forced RLS is lifted for the
    # statement and restored after.
    tables = ("engagements", "work_items", "assurance_work_items", "engagement_entities")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        WITH made AS (
            INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind,
                                    name, period_start, period_end, status, archived_at,
                                    created_by, created_at)
            SELECT e.tenant_id, e.id, e.client_id, e.client_entity_id, 'assurance', e.name,
                   e.fiscal_period_start, e.fiscal_period_end,
                   CASE WHEN e.status = 'archived' THEN 'archived' ELSE 'active' END,
                   CASE WHEN e.status = 'archived' THEN clock_timestamp() END,
                   e.created_by, e.created_at
            FROM engagements e
            RETURNING id, tenant_id, engagement_id
        )
        INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id, assurance_type,
                                          phase)
        SELECT m.id, m.tenant_id, m.engagement_id, e.type,
               CASE WHEN e.status = 'archived' THEN 'archived' ELSE 'planning' END
        FROM made m JOIN engagements e ON e.tenant_id = m.tenant_id AND e.id = m.engagement_id
        """
    )
    op.execute(
        "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role) "
        "SELECT tenant_id, id, client_entity_id, 'primary' FROM engagements"
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER engagements_work_item_defaults ON engagements")
    op.execute("DROP FUNCTION engagement_work_item_defaults()")
    op.execute("DROP TABLE engagement_entities")
    op.execute("DROP TABLE work_item_assignments")
    op.execute("DROP TABLE assurance_work_items")
    op.execute("DROP TABLE work_items")
