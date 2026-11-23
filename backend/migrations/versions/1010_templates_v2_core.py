"""K-03-T11 (S53; TASK-8901; SPEC-720 §4; ADR-213; K-03 §4.2; amber): templates v2 core
(methodology). Expand-only; K-01's `methodology_*` tables are not migrated (K-01 OQ-10).

- `engagement_templates`: one per methodology template (the template the firm edits as a whole).
- `template_versions`: draft · published · deprecated (display "Superseded" when `retired_at` is
  set). One draft per template (partial unique index). `template_version_guard` refuses DELETE of a
  published or deprecated row and any UPDATE of one except its deprecate and retire fields.
- Component tables, each carrying `template_version_id` and mutable only while that version is a
  draft (`template_component_guard`): sheet definitions, sheet columns (11 types, classification
  NOT NULL), sheet views, agent-column definitions, forms and form fields, requests, trigger
  defaults, report-template refs, skill pins and `scoping_rules`.
- `template_changes`: the frozen structural change list per version pair (insert-only).
- `agent_skills` and insert-only `agent_skill_versions` (K-05 adds the editor and the gate).
- Bootstrap: one `engagement_templates` row per methodology template and one published wrapper
  per published or superseded methodology version, and per version an engagement pins, so every
  existing pin has a template version (K-03-T12 links them).

Revision ID: 1010
Revises: 1003
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1010"
down_revision = "1003"
branch_labels = None
depends_on = None

COLUMN_TYPES = (
    "text", "number", "currency", "date", "single_select", "person", "linked_evidence",
    "linked_request", "linked_risk", "sign_off", "agent",
)  # fmt: skip
_TYPES = ", ".join(f"'{t}'" for t in COLUMN_TYPES)
_LEVELS = "'restricted', 'confidential', 'internal', 'public'"
_ACTOR = "current_setting('app.actor_id', true)"

# (table, columns body, insert columns); each also gets id, tenant_id, template_version_id.
COMPONENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "template_sheet_definitions",
        """
            sheet_key text NOT NULL CHECK (sheet_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$'),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            step_key text NULL CHECK (length(step_key) BETWEEN 1 AND 60),
            row_source text NOT NULL
                CHECK (row_source IN ('sample_set', 'control_set', 'group_structure', 'manual')),
            sections jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(sections) = 'array'),
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, template_version_id, sheet_key)
        """,
        ("sheet_key", "title", "step_key", "row_source", "sections", "position"),
    ),
    (
        "template_sheet_columns",
        f"""
            sheet_definition_id uuid NOT NULL,
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
            classification_reason text NULL CHECK (length(classification_reason) <= 500),
            source_binding jsonb NULL
                CHECK (source_binding IS NULL OR jsonb_typeof(source_binding) = 'object'),
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, sheet_definition_id, column_key),
            FOREIGN KEY (tenant_id, sheet_definition_id)
                REFERENCES template_sheet_definitions (tenant_id, id) ON DELETE CASCADE
        """,
        ("sheet_definition_id", "column_key", "name", "description", "type", "config",
         "required", "default_value", "validation", "client_visible", "classification",
         "classification_reason", "source_binding", "position"),
    ),
    (
        "template_sheet_views",
        """
            sheet_definition_id uuid NOT NULL,
            view_key text NOT NULL CHECK (view_key ~ '^[a-z][a-z0-9_]{0,59}$'),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
            filters jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(filters) = 'array'),
            sort jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(sort) = 'array'),
            visible_columns text[] NOT NULL DEFAULT '{}',
            group_by text NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, sheet_definition_id, view_key),
            FOREIGN KEY (tenant_id, sheet_definition_id)
                REFERENCES template_sheet_definitions (tenant_id, id) ON DELETE CASCADE
        """,
        ("sheet_definition_id", "view_key", "name", "filters", "sort", "visible_columns",
         "group_by", "position"),
    ),
    (
        "template_agent_column_defs",
        """
            sheet_column_id uuid NOT NULL,
            instruction_doc jsonb NOT NULL CHECK (jsonb_typeof(instruction_doc) = 'object'),
            output_type text NOT NULL CHECK (output_type IN ('single_select', 'text')),
            options jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(options) = 'array'),
            runs_as_capability text NOT NULL DEFAULT 'workpapers.column_filler'
                CHECK (runs_as_capability ~ '^[a-z_]+\\.[a-z_]+$'),
            skill_key text NULL,
            default_scope text NOT NULL DEFAULT 'empty_only'
                CHECK (default_scope IN ('all', 'empty_only', 'selected')),
            UNIQUE (tenant_id, sheet_column_id),
            CHECK (output_type = 'text' OR jsonb_array_length(options) >= 2),
            FOREIGN KEY (tenant_id, sheet_column_id)
                REFERENCES template_sheet_columns (tenant_id, id) ON DELETE CASCADE
        """,
        ("sheet_column_id", "instruction_doc", "output_type", "options", "runs_as_capability",
         "skill_key", "default_scope"),
    ),
    (
        "template_forms",
        """
            form_key text NOT NULL CHECK (form_key ~ '^[a-z][a-z0-9_]{0,59}$'),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, template_version_id, form_key)
        """,
        ("form_key", "title", "position"),
    ),
    (
        "template_form_fields",
        f"""
            form_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 200),
            type text NOT NULL CHECK (type IN ({_TYPES})),
            config jsonb NOT NULL DEFAULT '{{}}' CHECK (jsonb_typeof(config) = 'object'),
            required boolean NOT NULL DEFAULT false,
            classification text NOT NULL DEFAULT 'internal' CHECK (classification IN ({_LEVELS})),
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, form_id, field_key),
            FOREIGN KEY (tenant_id, form_id) REFERENCES template_forms (tenant_id, id)
                ON DELETE CASCADE
        """,
        ("form_id", "field_key", "label", "type", "config", "required", "classification",
         "position"),
    ),
    (
        "scoping_rules",
        """
            position integer NOT NULL CHECK (position >= 1),
            label text NULL CHECK (length(label) <= 200),
            group_op text NOT NULL DEFAULT 'and' CHECK (group_op IN ('and', 'or')),
            conditions jsonb NOT NULL
                CHECK (jsonb_typeof(conditions) = 'array' AND jsonb_array_length(conditions) >= 1),
            effect text NOT NULL CHECK (effect IN ('show', 'hide')),
            target_kind text NOT NULL
                CHECK (target_kind IN ('step', 'sheet', 'section', 'row', 'request_group')),
            target_ref text NOT NULL CHECK (length(target_ref) BETWEEN 1 AND 120),
            UNIQUE (tenant_id, template_version_id, position) DEFERRABLE INITIALLY DEFERRED
        """,
        ("position", "label", "group_op", "conditions", "effect", "target_kind", "target_ref"),
    ),
    (
        "template_requests",
        """
            request_key text NOT NULL CHECK (request_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$'),
            methodology_request_item_id uuid NULL,
            step_key text NULL CHECK (length(step_key) BETWEEN 1 AND 60),
            group_key text NULL CHECK (length(group_key) BETWEEN 1 AND 60),
            title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 300),
            shown_by_rule_id uuid NULL,
            position integer NOT NULL DEFAULT 0 CHECK (position >= 0),
            UNIQUE (tenant_id, template_version_id, request_key),
            FOREIGN KEY (methodology_request_item_id) REFERENCES methodology_request_items (id),
            FOREIGN KEY (tenant_id, shown_by_rule_id) REFERENCES scoping_rules (tenant_id, id)
                ON DELETE SET NULL (shown_by_rule_id)
        """,
        ("request_key", "methodology_request_item_id", "step_key", "group_key", "title",
         "shown_by_rule_id", "position"),
    ),
    (
        "template_trigger_defaults",
        """
            event text NOT NULL CHECK (event ~ '^[a-z_]+\\.[a-z_]+$'),
            capability_key text NOT NULL CHECK (capability_key ~ '^[a-z_]+\\.[a-z_]+$'),
            target_ref text NULL CHECK (length(target_ref) <= 120),
            condition_value jsonb NULL,
            enabled boolean NOT NULL DEFAULT true,
            UNIQUE (tenant_id, template_version_id, event, capability_key, target_ref)
        """,
        ("event", "capability_key", "target_ref", "condition_value", "enabled"),
    ),
    (
        "template_report_template_refs",
        """
            report_template_id uuid NOT NULL,
            report_template_version_id uuid NOT NULL,
            role text NOT NULL CHECK (role ~ '^[a-z][a-z0-9_]{0,59}$'),
            UNIQUE (tenant_id, template_version_id, role),
            FOREIGN KEY (tenant_id, report_template_id)
                REFERENCES report_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, report_template_version_id)
                REFERENCES report_template_versions (tenant_id, id)
        """,
        ("report_template_id", "report_template_version_id", "role"),
    ),
    (
        "template_skill_pins",
        """
            skill_key text NOT NULL CHECK (skill_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$'),
            skill_version_id uuid NOT NULL,
            UNIQUE (tenant_id, template_version_id, skill_key),
            FOREIGN KEY (tenant_id, skill_version_id)
                REFERENCES agent_skill_versions (tenant_id, id)
        """,
        ("skill_key", "skill_version_id"),
    ),
)  # fmt: skip

_VERSION_GUARD = """
    CREATE FUNCTION template_version_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_frozen constant text[] := ARRAY['status', 'deprecated_by', 'deprecated_at',
                                          'effective_to', 'retired_at', 'overlay_stats'];
    BEGIN
        IF TG_OP = 'DELETE' THEN
            IF OLD.status <> 'draft' THEN
                RAISE EXCEPTION 'template version % is %; it cannot be deleted', OLD.id,
                    OLD.status USING ERRCODE = 'AB409';
            END IF;
            RETURN OLD;
        END IF;
        IF OLD.status = 'draft' THEN
            IF NEW.status = 'deprecated' THEN
                RAISE EXCEPTION 'a draft is published before it is deprecated'
                    USING ERRCODE = 'AB409';
            END IF;
            RETURN NEW;
        END IF;
        IF (to_jsonb(NEW) - v_frozen) IS DISTINCT FROM (to_jsonb(OLD) - v_frozen)
           OR NOT (NEW.status = OLD.status
                   OR (OLD.status = 'published' AND NEW.status = 'deprecated'))
           OR (OLD.deprecated_at IS NOT NULL
               AND NEW.deprecated_at IS DISTINCT FROM OLD.deprecated_at)
           OR (OLD.retired_at IS NOT NULL AND NEW.retired_at IS DISTINCT FROM OLD.retired_at)
           OR (OLD.effective_to IS NOT NULL
               AND NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN
            RAISE EXCEPTION 'template version % is %; only its deprecate and retire fields move',
                OLD.id, OLD.status USING ERRCODE = 'AB409';
        END IF;
        RETURN NEW;
    END $$
"""

# Components move only while their version is a draft; the version row is locked FOR SHARE so a
# publish cannot interleave with a component write.
_COMPONENT_GUARD = """
    CREATE FUNCTION template_component_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_version uuid;
        v_status text;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            v_version := OLD.template_version_id;
        ELSE
            v_version := NEW.template_version_id;
            IF TG_OP = 'UPDATE' AND NEW.template_version_id <> OLD.template_version_id THEN
                RAISE EXCEPTION 'a component cannot move between versions'
                    USING ERRCODE = 'AB409';
            END IF;
        END IF;
        SELECT status INTO v_status FROM template_versions WHERE id = v_version FOR SHARE;
        IF v_status IS DISTINCT FROM 'draft' THEN
            IF TG_OP = 'DELETE' AND v_status IS NULL THEN
                RETURN OLD;  -- the draft itself is being discarded (cascade)
            END IF;
            RAISE EXCEPTION 'template version % is %; its components are frozen', v_version,
                coalesce(v_status, 'missing') USING ERRCODE = 'AB409';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engagement_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            methodology_template_id uuid NOT NULL,
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            family text NULL CHECK (family IN ('ebp', 'fs', 'ssars')),
            engagement_types text[] NOT NULL DEFAULT '{}',
            service_line text NOT NULL DEFAULT 'audit'
                CHECK (service_line IN ('audit', 'tax', 'cas', 'advisory')),
            owner_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, methodology_template_id),
            FOREIGN KEY (tenant_id, methodology_template_id)
                REFERENCES methodology_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, owner_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq >= 1),
            label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 40),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'deprecated')),
            methodology_version_id uuid NULL,
            based_on_version_id uuid NULL,
            effective_from date NULL,
            effective_to date NULL,
            retired_at timestamptz NULL,
            content_pack_release_ref text NULL CHECK (length(content_pack_release_ref) <= 120),
            overlay_stats jsonb NULL
                CHECK (overlay_stats IS NULL OR jsonb_typeof(overlay_stats) = 'object'),
            change_summary jsonb NOT NULL DEFAULT '{}'
                CHECK (jsonb_typeof(change_summary) = 'object'),
            fingerprint char(64) NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
            draft_etag integer NOT NULL DEFAULT 0 CHECK (draft_etag >= 0),
            origin text NOT NULL DEFAULT 'authored' CHECK (origin IN ('authored', 'bootstrap')),
            created_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            published_by uuid NULL,
            published_at timestamptz NULL,
            deprecated_by uuid NULL,
            deprecated_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_id, seq),
            FOREIGN KEY (tenant_id, template_id) REFERENCES engagement_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, methodology_version_id)
                REFERENCES methodology_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, based_on_version_id)
                REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, published_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, deprecated_by) REFERENCES memberships (tenant_id, user_id),
            CONSTRAINT template_versions_authored_by CHECK (
                origin = 'bootstrap' OR created_by IS NOT NULL),
            CONSTRAINT template_versions_published CHECK (
                status = 'draft' OR (published_at IS NOT NULL AND effective_from IS NOT NULL
                                     AND fingerprint IS NOT NULL
                                     AND (origin = 'bootstrap' OR published_by IS NOT NULL))),
            CONSTRAINT template_versions_deprecated CHECK (
                status <> 'deprecated' OR (deprecated_at IS NOT NULL
                                           AND deprecated_by IS NOT NULL)),
            CONSTRAINT template_versions_range CHECK (
                effective_to IS NULL OR effective_to >= effective_from),
            CONSTRAINT template_versions_not_self_based CHECK (based_on_version_id <> id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX template_versions_one_draft ON template_versions "
        "(tenant_id, template_id) WHERE status = 'draft'"
    )
    op.execute(
        "CREATE INDEX template_versions_by_methodology ON template_versions "
        "(tenant_id, methodology_version_id)"
    )
    op.execute(_VERSION_GUARD)
    op.execute(
        "CREATE TRIGGER template_version_guard BEFORE UPDATE OR DELETE ON template_versions "
        "FOR EACH ROW EXECUTE FUNCTION template_version_guard()"
    )

    op.execute(
        """
        CREATE TABLE agent_skills (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            skill_key text NOT NULL CHECK (skill_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$'),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            skill_group text NULL CHECK (length(skill_group) BETWEEN 1 AND 120),
            created_by uuid NOT NULL CHECK (created_by::text = current_setting('app.actor_id',
                                                                                true)),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, skill_key),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE agent_skill_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            skill_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            status text NOT NULL CHECK (status IN ('draft', 'published')),
            body_md text NOT NULL CHECK (length(body_md) BETWEEN 1 AND 60000),
            body_sha256 char(64) NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
            linked_step_keys text[] NOT NULL DEFAULT '{}',
            pass_bar integer NOT NULL DEFAULT 18 CHECK (pass_bar BETWEEN 1 AND 1000),
            eval_passed integer NULL CHECK (eval_passed >= 0),
            eval_total integer NULL CHECK (eval_total >= 0),
            source text NOT NULL CHECK (source IN ('authored', 'imported')),
            created_by uuid NOT NULL CHECK (created_by::text = current_setting('app.actor_id',
                                                                                true)),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            published_by uuid NULL,
            published_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, skill_id, version),
            FOREIGN KEY (tenant_id, skill_id) REFERENCES agent_skills (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, published_by) REFERENCES memberships (tenant_id, user_id),
            CHECK (eval_passed IS NULL OR eval_total IS NULL OR eval_passed <= eval_total),
            CHECK (status = 'draft' OR (published_by IS NOT NULL AND published_at IS NOT NULL))
        )
        """
    )

    op.execute(_COMPONENT_GUARD)
    for table, body, _ in COMPONENTS:
        op.execute(
            f"""
            CREATE TABLE {table} (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id uuid NOT NULL,
                template_version_id uuid NOT NULL,
                {body.strip()},
                UNIQUE (tenant_id, id),
                FOREIGN KEY (tenant_id, template_version_id)
                    REFERENCES template_versions (tenant_id, id) ON DELETE CASCADE
            )
            """
        )
        op.execute(f"CREATE INDEX {table}_by_version ON {table} (tenant_id, template_version_id)")
        op.execute(
            f"CREATE TRIGGER template_component_guard BEFORE INSERT OR UPDATE OR DELETE "
            f"ON {table} FOR EACH ROW EXECUTE FUNCTION template_component_guard()"
        )

    op.execute(
        """
        CREATE TABLE template_changes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            from_version_id uuid NOT NULL,
            to_version_id uuid NOT NULL,
            change_key text NOT NULL CHECK (length(change_key) BETWEEN 1 AND 200),
            kind text NOT NULL CHECK (kind IN ('added', 'changed', 'removed')),
            component text NOT NULL CHECK (component IN (
                'program', 'sheets', 'forms', 'request_list', 'triggers', 'report_templates',
                'skills', 'scoping_rules')),
            item_ref text NOT NULL CHECK (length(item_ref) BETWEEN 1 AND 200),
            summary jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(summary) = 'object'),
            frozen_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, from_version_id, to_version_id, change_key),
            FOREIGN KEY (tenant_id, from_version_id) REFERENCES template_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, to_version_id) REFERENCES template_versions (tenant_id, id),
            CHECK (from_version_id <> to_version_id)
        )
        """
    )

    tenant_table(op, "engagement_templates")
    insert_columns(
        op, "engagement_templates",
        ("id", "tenant_id", "methodology_template_id", "name", "family", "engagement_types",
         "service_line", "owner_user_id"),
    )  # fmt: skip
    op.execute("REVOKE UPDATE, DELETE ON engagement_templates FROM abacus_app")
    op.execute(
        "GRANT UPDATE (name, engagement_types, service_line, owner_user_id) "
        "ON engagement_templates TO abacus_app"
    )
    tenant_table(op, "template_versions")
    insert_columns(
        op, "template_versions",
        ("id", "tenant_id", "template_id", "seq", "label", "status", "methodology_version_id",
         "based_on_version_id", "effective_from", "content_pack_release_ref", "change_summary",
         "created_by"),
    )  # fmt: skip
    op.execute("REVOKE UPDATE ON template_versions FROM abacus_app")
    op.execute(
        "GRANT UPDATE (label, status, methodology_version_id, effective_from, effective_to, "
        "retired_at, overlay_stats, change_summary, fingerprint, draft_etag, published_by, "
        "published_at, deprecated_by, deprecated_at) ON template_versions TO abacus_app"
    )
    for table in ("agent_skills", "agent_skill_versions", "template_changes"):
        tenant_table(op, table)
        insert_only(op, table)
    insert_columns(
        op, "agent_skills", ("id", "tenant_id", "skill_key", "name", "skill_group", "created_by")
    )
    insert_columns(
        op, "agent_skill_versions",
        ("id", "tenant_id", "skill_id", "version", "status", "body_md", "body_sha256",
         "linked_step_keys", "pass_bar", "eval_passed", "eval_total", "source", "created_by",
         "published_by", "published_at"),
    )  # fmt: skip
    insert_columns(
        op, "template_changes",
        ("tenant_id", "from_version_id", "to_version_id", "change_key", "kind", "component",
         "item_ref", "summary"),
    )  # fmt: skip
    for table, _, columns in COMPONENTS:
        tenant_table(op, table)
        insert_columns(op, table, ("id", "tenant_id", "template_version_id", *columns))
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")

    _bootstrap()


def _bootstrap() -> None:
    """Owner-run backfill: RLS is unforced for the copy and forced again in this transaction."""
    tables = ("methodology_templates", "methodology_versions", "methodology_version_states",
              "engagements", "engagement_templates", "template_versions")  # fmt: skip
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        INSERT INTO engagement_templates (tenant_id, methodology_template_id, name, family,
                                          engagement_types, service_line)
        SELECT t.tenant_id, t.id, t.name, t.family, t.engagement_types,
               CASE WHEN 'tax' = ANY (t.engagement_types) AND NOT 'audit' = ANY
                         (t.engagement_types) THEN 'tax' ELSE 'audit' END
          FROM methodology_templates t
        """
    )
    # Wrap every published or superseded methodology version and every version an engagement
    # pins (whatever its state), in version order per template. Superseded ones are retired.
    op.execute(
        """
        WITH wrapped AS (
            SELECT v.tenant_id, v.id AS version_id, v.template_id, v.version, v.label,
                   v.source_fingerprint, v.imported_by, v.created_at,
                   s.status AS state, s.effective_from, s.effective_to, s.approved_by,
                   s.approved_at
              FROM methodology_versions v
              LEFT JOIN methodology_version_states s
                ON s.tenant_id = v.tenant_id AND s.version_id = v.id
             WHERE s.status IN ('published', 'superseded')
                OR EXISTS (SELECT 1 FROM engagements e
                            WHERE e.tenant_id = v.tenant_id AND e.methodology_version_id = v.id)
        )
        INSERT INTO template_versions (tenant_id, template_id, seq, label, status,
                                       methodology_version_id, effective_from, effective_to,
                                       retired_at, fingerprint, origin, published_by,
                                       published_at, change_summary)
        SELECT w.tenant_id, et.id,
               row_number() OVER (PARTITION BY w.tenant_id, w.template_id ORDER BY w.version),
               w.label, 'published', w.version_id,
               coalesce(w.effective_from, w.created_at::date),
               w.effective_to,
               CASE WHEN w.state = 'superseded'
                    THEN coalesce(w.effective_to::timestamptz, w.created_at) END,
               w.source_fingerprint, 'bootstrap',
               coalesce(w.approved_by, w.imported_by),
               coalesce(w.approved_at, w.created_at),
               jsonb_build_object('bootstrap', true, 'methodology_state',
                                  coalesce(w.state, 'unstated'))
          FROM wrapped w
          JOIN engagement_templates et
            ON et.tenant_id = w.tenant_id AND et.methodology_template_id = w.template_id
        """
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TABLE template_changes")
    for table, _, _ in reversed(COMPONENTS):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION template_component_guard()")
    op.execute("DROP TABLE agent_skill_versions")
    op.execute("DROP TABLE agent_skills")
    op.execute("DROP TABLE template_versions")
    op.execute("DROP FUNCTION template_version_guard()")
    op.execute("DROP TABLE engagement_templates")
