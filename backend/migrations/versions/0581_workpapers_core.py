"""Workpaper core for A-04 (A-04-T03, TASK-2710; A-04 §4.2 M1; DEC-1761). Expand-only.

SPEC-308's `0072` already holds `workpapers`, `workpaper_sections`, `workpaper_cells` (every value
a cell has held; the newest counts), `workpaper_cell_citations` and `workpaper_versions`, all
insert-only. A-04's M1 lands on them rather than beside them (DEC-1761):

- **Kept insert-only.** The plan's mutable `current_version_no`/`content_hash` on `workpapers` are
  derived from `workpaper_versions` (the newest), and a cell's current value stays its newest
  `workpaper_cells` row; `review.api.record_value` keeps the field history. Nothing gains UPDATE.
- **Columns added:** `workpapers.kind` and `program_step_keys`; `workpaper_sections.band_kind`;
  `workpaper_versions.produced_by_kind`, `agent_run_id`, `on_behalf_of_user_id`, `cause`;
  `workpaper_cells.section_key`, `row_key`, `col_key`, `value` (typed `{t, v}`), `value_state`,
  `suggestion_id`, `classification`, `updated_version_no`. The cell key CHECK widens to the
  structured keys ("S1.R3.value") beside the A1 keys; so does the citation's.
- **Scope on every row:** the child tables gain `engagement_id` and `work_item_id`, back-filled
  and then set by `workpaper_child_scope()` from the parent workpaper on every insert (whatever the
  caller sends), so `visible()` and A-07's archive lock cover each row.
- **New tables:** `attention_flags` (state moves open → converted or resolved, by column grant),
  `attention_flag_events` (insert-only) and `audit_procedures` (the plan's `procedures`: that name
  is fieldwork's SPEC-300 journal-entry procedure table since 0057). Each carries
  `engagement_id` and `work_item_id` and forced row-level security.

Revision ID: 0581
Revises: 0580
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0581"
down_revision = "0580"
branch_labels = None
depends_on = None

_A1 = "'^[A-Z]{1,2}[1-9][0-9]{0,3}$'"
_STRUCTURED = "'^[A-Za-z][A-Za-z0-9_]{0,19}([.][A-Za-z0-9_]{1,20}){1,3}$'"
_CHILDREN = (
    "workpaper_sections",
    "workpaper_cells",
    "workpaper_cell_citations",
    "workpaper_versions",
)

_SCOPE = """
    CREATE FUNCTION workpaper_child_scope() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        SELECT w.engagement_id, w.work_item_id
          INTO NEW.engagement_id, NEW.work_item_id
          FROM workpapers w
         WHERE w.tenant_id = NEW.tenant_id AND w.id = NEW.workpaper_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'workpaper_not_found' USING ERRCODE = '23503';
        END IF;
        RETURN NEW;
    END
    $$
"""


def _scope_children() -> None:
    op.execute(_SCOPE)
    for table in (*_CHILDREN, "attention_flags", "attention_flag_events"):
        if table in _CHILDREN:
            op.execute(
                f"ALTER TABLE {table} ADD COLUMN engagement_id uuid, ADD COLUMN work_item_id uuid"
            )
            op.execute(
                f"UPDATE {table} c SET engagement_id = w.engagement_id, "
                "work_item_id = w.work_item_id FROM workpapers w "
                "WHERE w.tenant_id = c.tenant_id AND w.id = c.workpaper_id"
            )
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN engagement_id SET NOT NULL, "
                "ALTER COLUMN work_item_id SET NOT NULL"
            )
        op.execute(
            f"CREATE TRIGGER {table}_scope BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION workpaper_child_scope()"
        )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE workpapers
            ADD COLUMN kind text NULL CHECK (kind IN ('general_audit_planning',
                'risk_assessment', 'internal_control', 'service_organizations')),
            ADD COLUMN program_step_keys text[] NOT NULL DEFAULT '{}'
                CHECK (cardinality(program_step_keys) <= 200)
        """
    )
    op.execute(
        "ALTER TABLE workpapers ADD CONSTRAINT workpapers_scope "
        "UNIQUE (tenant_id, engagement_id, work_item_id, id)"
    )
    op.execute(
        """
        ALTER TABLE workpaper_sections
            ADD COLUMN band_kind text NOT NULL DEFAULT 'section'
                CHECK (band_kind IN ('section', 'menu', 'sheet'))
        """
    )
    op.execute(
        """
        ALTER TABLE workpaper_versions
            ADD COLUMN produced_by_kind text NOT NULL DEFAULT 'human'
                CHECK (produced_by_kind IN ('agent', 'human')),
            ADD COLUMN agent_run_id uuid NULL,
            ADD COLUMN on_behalf_of_user_id uuid NULL,
            ADD COLUMN cause text NULL CHECK (cause IN ('draft', 'adopt', 'edit', 'restore')),
            ADD CONSTRAINT workpaper_versions_agent_run
                CHECK ((produced_by_kind = 'agent') = (agent_run_id IS NOT NULL))
        """
    )
    for table in ("workpaper_cells", "workpaper_cell_citations"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_cell_key_check")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_cell_key_check "
            f"CHECK (cell_key ~ {_A1} OR cell_key ~ {_STRUCTURED})"
        )
    op.execute(
        """
        ALTER TABLE workpaper_cells
            ADD COLUMN section_key text NULL CHECK (section_key ~ '^[a-z][a-z0-9_]{0,39}$'),
            ADD COLUMN row_key text NULL CHECK (row_key ~ '^[A-Za-z0-9_]{1,40}$'),
            ADD COLUMN col_key text NULL CHECK (col_key ~ '^[A-Za-z0-9_]{1,40}$'),
            ADD COLUMN value jsonb NULL CHECK (value IS NULL OR (jsonb_typeof(value) = 'object'
                AND value ? 't'
                AND value->>'t' IN ('decimal', 'text', 'date', 'bool', 'percent', 'empty'))),
            ADD COLUMN value_state text NOT NULL DEFAULT 'human'
                CHECK (value_state IN ('empty', 'suggested', 'adopted', 'edited', 'human')),
            ADD COLUMN suggestion_id uuid NULL,
            ADD COLUMN classification text NOT NULL DEFAULT 'confidential'
                CHECK (classification IN ('public', 'internal', 'confidential', 'restricted')),
            ADD COLUMN updated_version_no integer NULL CHECK (updated_version_no > 0),
            ADD CONSTRAINT workpaper_cells_suggested
                CHECK (value_state NOT IN ('suggested', 'adopted') OR suggestion_id IS NOT NULL)
        """
    )
    op.execute(
        """
        CREATE TABLE attention_flags (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            section_key text NOT NULL CHECK (section_key ~ '^[a-z][a-z0-9_]{0,39}$'),
            row_key text NULL CHECK (row_key ~ '^[A-Za-z0-9_]{1,40}$'),
            kind text NOT NULL CHECK (kind IN ('pbc_gap')),
            text text NOT NULL CHECK (length(btrim(text)) BETWEEN 1 AND 2000),
            state text NOT NULL DEFAULT 'open'
                CHECK (state IN ('open', 'converted', 'resolved')),
            converted_to_kind text NULL
                CHECK (converted_to_kind IN ('request_item', 'review_note')),
            converted_to_id uuid NULL,
            created_by uuid NOT NULL,
            created_by_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (created_by_kind IN ('agent', 'human')),
            agent_run_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, workpaper_id, id),
            CONSTRAINT attention_flags_converted CHECK (
                (state = 'converted') = (converted_to_kind IS NOT NULL)
                AND (converted_to_kind IS NULL) = (converted_to_id IS NULL)
            ),
            CONSTRAINT attention_flags_agent_run
                CHECK ((created_by_kind = 'agent') = (agent_run_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id, workpaper_id)
                REFERENCES workpapers (tenant_id, engagement_id, work_item_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX attention_flags_open ON attention_flags (tenant_id, workpaper_id) "
        "WHERE state = 'open'"
    )
    tenant_table(op, "attention_flags")
    op.execute("REVOKE DELETE ON attention_flags FROM abacus_app")
    insert_columns(
        op,
        "attention_flags",
        (
            "tenant_id",
            "workpaper_id",
            "section_key",
            "row_key",
            "kind",
            "text",
            "created_by",
            "agent_run_id",
        ),
    )
    op.execute("REVOKE UPDATE ON attention_flags FROM abacus_app")
    op.execute(
        "GRANT UPDATE (state, converted_to_kind, converted_to_id) ON attention_flags TO abacus_app"
    )
    op.execute(
        """
        CREATE TABLE attention_flag_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            workpaper_id uuid NOT NULL,
            flag_id uuid NOT NULL,
            event text NOT NULL
                CHECK (event IN ('raised', 'reminded', 'escalated', 'converted', 'resolved')),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind IN ('agent', 'human', 'system')),
            actor_user_id uuid NULL,
            agent_run_id uuid NULL,
            ref jsonb NULL CHECK (ref IS NULL OR jsonb_typeof(ref) = 'object'),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT attention_flag_events_actor CHECK (
                (actor_kind = 'human') = (actor_user_id IS NOT NULL)
                AND (actor_kind = 'agent') = (agent_run_id IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, workpaper_id, flag_id)
                REFERENCES attention_flags (tenant_id, workpaper_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX attention_flag_events_by_flag ON attention_flag_events (tenant_id, flag_id, at)"
    )
    tenant_table(op, "attention_flag_events")
    insert_only(op, "attention_flag_events")
    insert_columns(
        op,
        "attention_flag_events",
        ("tenant_id", "workpaper_id", "flag_id", "event", "actor_user_id", "agent_run_id", "ref"),
    )
    _scope_children()
    op.execute(
        """
        CREATE TABLE audit_procedures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            methodology_version_id uuid NOT NULL,
            program_step_key text NOT NULL
                CHECK (program_step_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$'),
            level text NOT NULL
                CHECK (level IN ('foundation', 'planning', 'testing', 'completion')),
            mandatory boolean NOT NULL,
            tailored boolean NOT NULL DEFAULT false,
            tailored_rationale text NULL
                CHECK (length(btrim(tailored_rationale)) BETWEEN 1 AND 2000),
            status text NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'in_progress', 'in_review', 'complete')),
            linked_work jsonb NULL CHECK (linked_work IS NULL OR (
                jsonb_typeof(linked_work) = 'object'
                AND linked_work->>'kind' IN ('workpaper', 'sheet', 'screens'))),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, program_step_key),
            CONSTRAINT audit_procedures_mandatory_untailored CHECK (NOT (mandatory AND tailored)),
            CONSTRAINT audit_procedures_tailored_reason
                CHECK (NOT tailored OR tailored_rationale IS NOT NULL),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, methodology_version_id)
                REFERENCES methodology_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "audit_procedures")
    op.execute("REVOKE DELETE ON audit_procedures FROM abacus_app")
    insert_columns(
        op,
        "audit_procedures",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "methodology_version_id",
            "program_step_key",
            "level",
            "mandatory",
            "created_by",
        ),
    )
    op.execute("REVOKE UPDATE ON audit_procedures FROM abacus_app")
    op.execute(
        "GRANT UPDATE (tailored, tailored_rationale, status, linked_work) "
        "ON audit_procedures TO abacus_app"
    )
    # The app may insert the new columns of the 0072 tables (the scope columns stay trigger-set).
    op.execute("GRANT INSERT (kind, program_step_keys) ON workpapers TO abacus_app")
    op.execute("GRANT INSERT (band_kind) ON workpaper_sections TO abacus_app")
    op.execute(
        "GRANT INSERT (produced_by_kind, agent_run_id, on_behalf_of_user_id, cause) "
        "ON workpaper_versions TO abacus_app"
    )
    op.execute(
        "GRANT INSERT (section_key, row_key, col_key, value, value_state, suggestion_id, "
        "classification, updated_version_no) ON workpaper_cells TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_procedures")
    op.execute("DROP TABLE attention_flag_events")
    op.execute("DROP TABLE attention_flags")
    for table in _CHILDREN:
        op.execute(f"DROP TRIGGER {table}_scope ON {table}")
        op.execute(f"ALTER TABLE {table} DROP COLUMN engagement_id, DROP COLUMN work_item_id")
    op.execute("DROP FUNCTION workpaper_child_scope()")
    op.execute(
        """
        ALTER TABLE workpaper_cells
            DROP CONSTRAINT workpaper_cells_suggested,
            DROP COLUMN section_key, DROP COLUMN row_key, DROP COLUMN col_key,
            DROP COLUMN value, DROP COLUMN value_state, DROP COLUMN suggestion_id,
            DROP COLUMN classification, DROP COLUMN updated_version_no
        """
    )
    for table in ("workpaper_cells", "workpaper_cell_citations"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_cell_key_check")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_cell_key_check CHECK (cell_key ~ {_A1})"
        )
    op.execute(
        """
        ALTER TABLE workpaper_versions
            DROP CONSTRAINT workpaper_versions_agent_run,
            DROP COLUMN produced_by_kind, DROP COLUMN agent_run_id,
            DROP COLUMN on_behalf_of_user_id, DROP COLUMN cause
        """
    )
    op.execute("ALTER TABLE workpaper_sections DROP COLUMN band_kind")
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_scope")
    op.execute("ALTER TABLE workpapers DROP COLUMN kind, DROP COLUMN program_step_keys")
