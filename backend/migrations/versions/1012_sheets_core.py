"""K-03-T13 (S53; TASK-8903; SPEC-721; ADR-213; K-03 §4.2; amber): the Sheets engine core
(workpapers). Expand-only.

- `sheets`: one per procedure (or per work item), made from a pinned template version's sheet
  definition; `kind` internal or request-facing. Lock is computed from reviewer sign-offs, never
  stored.
- `sheet_columns` (11 types, classification NOT NULL; a client-visible column on an internal sheet
  is refused by trigger), `sheet_sections`, `sheet_rows`, `sheet_cells` (value_state empty · human
  · suggested · adopted · edited; history in P-04's `field_value_versions`), `sheet_views`,
  `sheet_row_links`.
- `agent_columns`, `agent_column_previews`, `agent_column_runs`, `agent_column_run_rows`.
- `program_procedures.scoped_out_by_rule` (A-04's table; `linked_work` already admits `sheet`).

Every child table carries the sheet's `engagement_id` and `work_item_id` under one composite
foreign key, so `archived_guard` (attached by `tenant_table`) refuses writes to an archived
engagement's or locked work item's sheet. Codes follow the SH-1 contract (`sheets_contract.py`,
DEC-5850): the agent column's type is `agent` and an edited suggestion's state is `edited`.

Revision ID: 1012
Revises: 1011
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1012"
down_revision = "1011"
branch_labels = None
depends_on = None

COLUMN_TYPES = (
    "text", "number", "currency", "date", "single_select", "person", "linked_evidence",
    "linked_request", "linked_risk", "sign_off", "agent",
)  # fmt: skip
_TYPES = ", ".join(f"'{t}'" for t in COLUMN_TYPES)
_LEVELS = "'restricted', 'confidential', 'internal', 'public'"
_SCOPE = "tenant_id uuid NOT NULL,\n            engagement_id uuid NOT NULL,\n" \
    "            work_item_id uuid NOT NULL,\n            sheet_id uuid NOT NULL"  # fmt: skip
_SHEET_FK = (
    "FOREIGN KEY (tenant_id, engagement_id, work_item_id, sheet_id)\n"
    "                REFERENCES sheets (tenant_id, engagement_id, work_item_id, id)"
)
_PERSON = "FOREIGN KEY (tenant_id, {col}) REFERENCES memberships (tenant_id, user_id)"


def _person(col: str) -> str:
    return _PERSON.format(col=col)


_CLIENT_VISIBLE_GUARD = """
    CREATE FUNCTION sheet_column_client_visible_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF NEW.client_visible AND (SELECT kind FROM sheets WHERE id = NEW.sheet_id) = 'internal'
        THEN
            RAISE EXCEPTION 'a column on an internal sheet is never client-visible'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE sheets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            procedure_id uuid NULL,
            sheet_key text NOT NULL CHECK (sheet_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{{0,59}}$'),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            template_version_id uuid NOT NULL,
            sheet_definition_id uuid NOT NULL,
            kind text NOT NULL DEFAULT 'internal' CHECK (kind IN ('internal', 'request_facing')),
            sample_set_id uuid NULL,
            sample_version integer NULL CHECK (sample_version >= 1),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, work_item_id, id),
            UNIQUE (tenant_id, work_item_id, sheet_key),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, procedure_id) REFERENCES program_procedures (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, sheet_definition_id)
                REFERENCES template_sheet_definitions (tenant_id, id),
            FOREIGN KEY (tenant_id, sample_set_id) REFERENCES sample_sets (tenant_id, id),
            {_person("created_by")},
            CHECK ((sample_set_id IS NULL) = (sample_version IS NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sheet_columns (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            column_key text NOT NULL CHECK (column_key ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
            description text NULL CHECK (length(description) <= 1000),
            type text NOT NULL CHECK (type IN ({_TYPES})),
            config jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(config) = 'object'),
            required boolean NOT NULL DEFAULT false,
            default_value jsonb NULL,
            validation jsonb NULL
                CHECK (validation IS NULL OR jsonb_typeof(validation) = 'object'),
            client_visible boolean NOT NULL DEFAULT false,
            classification text NOT NULL CHECK (classification IN ({_LEVELS})),
            classification_reason text NULL CHECK (length(classification_reason) <= 300),
            origin text NOT NULL CHECK (origin IN ('template', 'engagement')),
            template_column_ref uuid NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            width integer NOT NULL DEFAULT 160 CHECK (width BETWEEN 40 AND 800),
            frozen boolean NOT NULL DEFAULT false,
            deleted_at timestamptz NULL,
            deleted_by uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, sheet_id, id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, template_column_ref)
                REFERENCES template_sheet_columns (tenant_id, id),
            {_person("deleted_by")},
            CHECK ((origin = 'template') = (template_column_ref IS NOT NULL)),
            CHECK ((deleted_at IS NULL) = (deleted_by IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX sheet_columns_live_key ON sheet_columns "
        "(tenant_id, sheet_id, column_key) WHERE deleted_at IS NULL"
    )
    op.execute(_CLIENT_VISIBLE_GUARD)
    op.execute(
        "CREATE TRIGGER sheet_column_client_visible_guard BEFORE INSERT OR UPDATE OF "
        "client_visible ON sheet_columns FOR EACH ROW "
        "EXECUTE FUNCTION sheet_column_client_visible_guard()"
    )
    op.execute(
        f"""
        CREATE TABLE sheet_sections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            section_key text NOT NULL
                CHECK (section_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{{0,59}}$'),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            parent_section_key text NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            totals_spec jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(totals_spec) = 'object'),
            UNIQUE (tenant_id, sheet_id, section_key),
            {_SHEET_FK},
            CHECK (parent_section_key IS DISTINCT FROM section_key)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sheet_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            row_key text NOT NULL CHECK (row_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{{0,59}}$'),
            section_key text NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            source_ref jsonb NOT NULL CHECK (jsonb_typeof(source_ref) = 'object'
                AND source_ref->>'kind' IN ('sample_item', 'control', 'entity', 'manual')),
            scoped_out_by_rule boolean NOT NULL DEFAULT false,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, sheet_id, row_key),
            UNIQUE (tenant_id, sheet_id, id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, sheet_id, section_key)
                REFERENCES sheet_sections (tenant_id, sheet_id, section_key),
            {_person("created_by")}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sheet_cells (
            {_SCOPE},
            row_id uuid NOT NULL,
            column_id uuid NOT NULL,
            value jsonb NULL,
            value_state text NOT NULL DEFAULT 'empty'
                CHECK (value_state IN ('empty', 'human', 'suggested', 'adopted', 'edited')),
            suggestion_id uuid NULL,
            previous_value jsonb NULL,
            last_edited_by uuid NULL,
            last_edited_at timestamptz NULL,
            PRIMARY KEY (row_id, column_id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, sheet_id, row_id)
                REFERENCES sheet_rows (tenant_id, sheet_id, id),
            FOREIGN KEY (tenant_id, sheet_id, column_id)
                REFERENCES sheet_columns (tenant_id, sheet_id, id),
            FOREIGN KEY (suggestion_id) REFERENCES suggestions (id),
            {_person("last_edited_by")},
            CHECK ((value_state = 'empty') = (value IS NULL)),
            CHECK (value_state NOT IN ('suggested', 'adopted', 'edited')
                   OR suggestion_id IS NOT NULL),
            CHECK (value_state NOT IN ('human', 'adopted', 'edited')
                   OR last_edited_by IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sheet_views (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            view_key text NOT NULL CHECK (view_key ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
            filters jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(filters) = 'array'),
            sort jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(sort) = 'array'),
            visible_columns text[] NOT NULL DEFAULT '{{}}',
            group_by text NULL,
            created_by uuid NOT NULL,
            shared boolean NOT NULL DEFAULT false,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, sheet_id, view_key),
            {_SHEET_FK},
            {_person("created_by")}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE sheet_row_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            row_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('evidence', 'request', 'risk')),
            target_id uuid NOT NULL,
            linked_by uuid NOT NULL,
            linked_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, row_id, kind, target_id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, sheet_id, row_id)
                REFERENCES sheet_rows (tenant_id, sheet_id, id),
            {_person("linked_by")}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE agent_columns (
            {_SCOPE},
            sheet_column_id uuid PRIMARY KEY,
            instruction_doc jsonb NOT NULL CHECK (jsonb_typeof(instruction_doc) = 'object'),
            instruction_hash char(64) NOT NULL CHECK (instruction_hash ~ '^[0-9a-f]{{64}}$'),
            mention_refs jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(mention_refs) = 'array'),
            output_type text NOT NULL CHECK (output_type IN ('single_select', 'text')),
            options jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(options) = 'array'),
            runs_as_capability text NOT NULL DEFAULT 'workpapers.column_filler'
                CHECK (runs_as_capability ~ '^[a-z_]+\\.[a-z_]+$'),
            skill_key text NULL,
            skill_version_id uuid NULL,
            default_scope text NOT NULL DEFAULT 'empty_only'
                CHECK (default_scope IN ('all', 'empty_only', 'selected')),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'saved')),
            saved_by uuid NULL,
            saved_at timestamptz NULL,
            saved_preview_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, sheet_column_id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, sheet_id, sheet_column_id)
                REFERENCES sheet_columns (tenant_id, sheet_id, id),
            FOREIGN KEY (tenant_id, skill_version_id)
                REFERENCES agent_skill_versions (tenant_id, id),
            {_person("saved_by")},
            CHECK (output_type = 'text' OR jsonb_array_length(options) >= 2),
            CHECK (status = 'draft' OR (saved_by IS NOT NULL AND saved_at IS NOT NULL
                                        AND saved_preview_id IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE agent_column_previews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            agent_column_id uuid NOT NULL,
            instruction_hash char(64) NOT NULL CHECK (instruction_hash ~ '^[0-9a-f]{{64}}$'),
            row_ids uuid[] NOT NULL CHECK (cardinality(row_ids) BETWEEN 1 AND 3),
            agent_run_id uuid NULL,
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
            results jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(results) = 'array'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, agent_column_id)
                REFERENCES agent_columns (tenant_id, sheet_column_id),
            FOREIGN KEY (agent_run_id) REFERENCES agent_runs (id),
            {_person("created_by")}
        )
        """
    )
    op.execute(
        "ALTER TABLE agent_columns ADD CONSTRAINT agent_columns_saved_preview_fkey "
        "FOREIGN KEY (tenant_id, saved_preview_id) "
        "REFERENCES agent_column_previews (tenant_id, id)"
    )
    op.execute(
        f"""
        CREATE TABLE agent_column_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            agent_column_id uuid NOT NULL,
            agent_run_id uuid NULL,
            run_number integer NOT NULL CHECK (run_number >= 1),
            scope text NOT NULL CHECK (scope IN ('all', 'empty_only', 'selected')),
            rows_targeted integer NOT NULL CHECK (rows_targeted >= 0),
            rows_now integer NOT NULL DEFAULT 0 CHECK (rows_now >= 0),
            rows_on_arrival integer NOT NULL DEFAULT 0 CHECK (rows_on_arrival >= 0),
            estimate_minutes numeric(8, 1) NOT NULL CHECK (estimate_minutes >= 0),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'cancelled', 'succeeded', 'failed')),
            initiator_kind text NOT NULL CHECK (initiator_kind IN ('person', 'trigger')),
            trigger_id uuid NULL,
            budget_override_by uuid NULL,
            started_by uuid NOT NULL,
            started_at timestamptz NOT NULL DEFAULT abacus_now(),
            stopped_by uuid NULL,
            stopped_at timestamptz NULL,
            finished_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, agent_column_id, run_number),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, agent_column_id)
                REFERENCES agent_columns (tenant_id, sheet_column_id),
            FOREIGN KEY (agent_run_id) REFERENCES agent_runs (id),
            {_person("started_by")},
            {_person("stopped_by")},
            {_person("budget_override_by")},
            CHECK ((initiator_kind = 'trigger') = (trigger_id IS NOT NULL)),
            CHECK (rows_now + rows_on_arrival <= rows_targeted),
            CHECK ((stopped_at IS NULL) = (stopped_by IS NULL)),
            CHECK (status <> 'cancelled' OR stopped_at IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX agent_column_runs_one_live ON agent_column_runs "
        "(tenant_id, agent_column_id) WHERE status IN ('queued', 'running')"
    )
    op.execute(
        f"""
        CREATE TABLE agent_column_run_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {_SCOPE},
            run_id uuid NOT NULL,
            row_id uuid NOT NULL,
            state text NOT NULL DEFAULT 'queued' CHECK (state IN (
                'queued', 'running', 'waiting_on_inputs', 'succeeded', 'failed', 'cancelled',
                'skipped_adopted')),
            suggestion_id uuid NULL,
            child_run_id uuid NULL,
            evidence_version_id uuid NULL,
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, run_id, row_id),
            {_SHEET_FK},
            FOREIGN KEY (tenant_id, run_id) REFERENCES agent_column_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, sheet_id, row_id)
                REFERENCES sheet_rows (tenant_id, sheet_id, id),
            FOREIGN KEY (suggestion_id) REFERENCES suggestions (id),
            FOREIGN KEY (child_run_id) REFERENCES agent_runs (id),
            CHECK (state <> 'succeeded' OR suggestion_id IS NOT NULL),
            CHECK (state <> 'failed' OR failure_code IS NOT NULL)
        )
        """
    )
    op.execute(
        "ALTER TABLE program_procedures ADD COLUMN scoped_out_by_rule boolean NOT NULL "
        "DEFAULT false"
    )
    op.execute("GRANT UPDATE (scoped_out_by_rule) ON program_procedures TO abacus_app")
    for index in (
        "sheets_by_engagement ON sheets (tenant_id, engagement_id)",
        "sheet_rows_by_section ON sheet_rows (tenant_id, sheet_id, section_key, position)",
        "sheet_cells_by_column ON sheet_cells (tenant_id, column_id)",
        "agent_column_run_rows_waiting ON agent_column_run_rows (tenant_id, row_id) "
        "WHERE state = 'waiting_on_inputs'",
    ):
        op.execute(f"CREATE INDEX {index}")

    for table, inserts, updates in GRANTS:
        tenant_table(op, table)
        insert_columns(op, table, inserts)
        if updates is None:
            insert_only(op, table)
            continue
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        if updates:
            op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    # A manual row and a saved view may be removed; the sheet's other rows never are.
    op.execute("GRANT DELETE ON sheet_views, sheet_row_links TO abacus_app")


_S = ("tenant_id", "engagement_id", "work_item_id", "sheet_id")
# (table, insert columns, update columns; None = insert-only)
GRANTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...] | None], ...] = (
    ("sheets",
     ("id", "tenant_id", "engagement_id", "work_item_id", "procedure_id", "sheet_key", "title",
      "template_version_id", "sheet_definition_id", "kind", "sample_set_id", "sample_version",
      "created_by"),
     ("title", "sample_set_id", "sample_version", "version")),
    ("sheet_columns",
     ("id", *_S, "column_key", "name", "description", "type", "config", "required",
      "default_value", "validation", "client_visible", "classification",
      "classification_reason", "origin", "template_column_ref", "position", "width", "frozen"),
     ("name", "description", "config", "required", "default_value", "validation",
      "client_visible", "classification", "classification_reason", "position", "width",
      "frozen", "deleted_at", "deleted_by", "version")),
    ("sheet_sections",
     (*_S, "section_key", "title", "parent_section_key", "position", "totals_spec"),
     ("title", "position", "totals_spec")),
    ("sheet_rows",
     ("id", *_S, "row_key", "section_key", "position", "source_ref", "scoped_out_by_rule",
      "created_by"),
     ("section_key", "position", "scoped_out_by_rule", "row_version")),
    ("sheet_cells",
     (*_S, "row_id", "column_id", "value", "value_state", "suggestion_id", "previous_value",
      "last_edited_by", "last_edited_at"),
     ("value", "value_state", "suggestion_id", "previous_value", "last_edited_by",
      "last_edited_at")),
    ("sheet_views",
     ("id", *_S, "view_key", "name", "filters", "sort", "visible_columns", "group_by",
      "created_by", "shared"),
     ("name", "filters", "sort", "visible_columns", "group_by", "shared", "version")),
    ("sheet_row_links", (*_S, "row_id", "kind", "target_id", "linked_by"), ()),
    ("agent_columns",
     (*_S, "sheet_column_id", "instruction_doc", "instruction_hash", "mention_refs",
      "output_type", "options", "runs_as_capability", "skill_key", "skill_version_id",
      "default_scope"),
     ("instruction_doc", "instruction_hash", "mention_refs", "output_type", "options",
      "skill_key", "skill_version_id", "default_scope", "status", "saved_by", "saved_at",
      "saved_preview_id", "version")),
    ("agent_column_previews",
     ("id", *_S, "agent_column_id", "instruction_hash", "row_ids", "created_by"),
     ("agent_run_id", "status", "results")),
    ("agent_column_runs",
     ("id", *_S, "agent_column_id", "run_number", "scope", "rows_targeted", "rows_now",
      "rows_on_arrival", "estimate_minutes", "initiator_kind", "trigger_id",
      "budget_override_by", "started_by"),
     ("agent_run_id", "rows_now", "rows_on_arrival", "status", "stopped_by", "stopped_at",
      "finished_at")),
    ("agent_column_run_rows",
     (*_S, "run_id", "row_id", "state"),
     ("state", "suggestion_id", "child_run_id", "evidence_version_id", "failure_code",
      "updated_at")),
)  # fmt: skip


def downgrade() -> None:
    op.execute("ALTER TABLE program_procedures DROP COLUMN scoped_out_by_rule")
    op.execute("ALTER TABLE agent_columns DROP CONSTRAINT agent_columns_saved_preview_fkey")
    for table in ("agent_column_run_rows", "agent_column_runs", "agent_column_previews",
                  "agent_columns", "sheet_row_links", "sheet_views", "sheet_cells", "sheet_rows",
                  "sheet_sections", "sheet_columns", "sheets"):  # fmt: skip
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION sheet_column_client_visible_guard()")
