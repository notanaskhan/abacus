"""Statements v1, DEC-80's canonical model (A-06-T19; A-06 §4.2; AUD-20; DEC-2209; expand-only).

`reporting` (the statements; owner `reporting`):
- `statement_documents`: one financial-statement document per audit work item and framework,
  its status and management-approval state (DEC-80; ADR P-59 adds the editor later).
- `statement_versions` (insert-only): each draft from a TB snapshot and the approved entries,
  with who drafted it (system or a person) and the content hash; "out of date" is computed.
- `line_items` and `linked_values` (insert-only per version): each line's value per year and its
  source (`tb_linked`, `formula`, `override`, `stale_override`); **an override needs its reason**.
- `tie_out_runs` (insert-only): code's tie-out of a version.
- `disclosure_checklist_answers`: one answer per item (yes, no, na), **N/A needs its reason**;
  history through `field_value_versions` (field owner `disclosure_checklist`).
- `statement_approvals` (insert-only, the session's own human actor only): sent for approval,
  approved by management, commented.

`methodology` (firm content, owner `methodology`): `disclosure_checklist_templates` and their
versions (items as JSON, published by a person). No checklist text is inserted here (AGENTS 16;
licensed text only under ADR-056).

Revision ID: 0660
Revises: 0659
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0660"
down_revision = "0659"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true) "
    "CHECK (actor_id = current_setting('app.actor_id', true))"
)
_SHA = "~ '^[0-9a-f]{64}$'"
_INSERT_ONLY = (
    "statement_versions",
    "line_items",
    "linked_values",
    "tie_out_runs",
    "statement_approvals",
)
_TABLES = (
    "disclosure_checklist_templates",
    "disclosure_checklist_template_versions",
    "statement_documents",
    "statement_versions",
    "line_items",
    "linked_values",
    "tie_out_runs",
    "disclosure_checklist_answers",
    "statement_approvals",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "disclosure_checklist_templates": ("tenant_id", "framework_key", "name", "created_by"),
    "disclosure_checklist_template_versions": (
        "tenant_id",
        "template_id",
        "version",
        "items",
        "source_file_sha256",
        "imported_by",
    ),
    "statement_documents": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "kind",
        "framework_key",
        "checklist_template_version_id",
    ),
    "statement_versions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "statement_document_id",
        "version_no",
        "source_snapshot_id",
        "adjustments_hash",
        "drafted_by_kind",
        "run_id",
        "initiator_user_id",
        "engine_version",
        "content_hash",
    ),
    "line_items": (
        "tenant_id",
        "statement_version_id",
        "statement_key",
        "section_key",
        "line_key",
        "label",
        "position",
        "note_ref",
    ),
    "linked_values": (
        "tenant_id",
        "line_item_id",
        "year",
        "value",
        "source",
        "source_ref",
        "citation_ids",
        "override_reason",
    ),
    "tie_out_runs": (
        "tenant_id",
        "statement_version_id",
        "engine_version",
        "inputs_hash",
        "total",
        "tied",
        "off",
    ),
    "disclosure_checklist_answers": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "statement_document_id",
        "template_version_id",
        "item_key",
        "answer",
        "note_ref",
        "reason",
        "state",
        "suggestion_id",
        "answered_by",
        "adopted_by",
    ),
    "statement_approvals": (
        "tenant_id",
        "statement_version_id",
        "event",
        "actor_principal",
        "channel",
        "approval_item_ref",
        "deliverable_ref",
        "evidence_version_id",
    ),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "disclosure_checklist_template_versions": ("status", "published_by", "published_at"),
    "statement_documents": (
        "current_version_no",
        "status",
        "management_approval",
        "row_version",
        "updated_at",
    ),
    "disclosure_checklist_answers": (
        "answer",
        "note_ref",
        "reason",
        "state",
        "suggestion_id",
        "answered_by",
        "adopted_by",
        "reviewed_by",
        "version",
        "updated_at",
    ),
}

_IMMUTABLE = """
    CREATE FUNCTION statement_rows_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        RAISE EXCEPTION 'statement versions, lines, values, tie-outs and approvals are insert-only'
            USING ERRCODE = 'insufficient_privilege';
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE disclosure_checklist_templates (
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
        f"""
        CREATE TABLE disclosure_checklist_template_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            items jsonb NOT NULL CHECK (jsonb_typeof(items) = 'array'),
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
                REFERENCES disclosure_checklist_templates (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statement_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL DEFAULT 'financial_statements'
                CHECK (kind IN ('financial_statements')),
            framework_key text NOT NULL CHECK (framework_key ~ '^[a-z][a-z0-9_]{{1,39}}$'),
            checklist_template_version_id uuid NULL,
            current_version_no integer NOT NULL DEFAULT 0 CHECK (current_version_no >= 0),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'in_review', 'final', 'signed_off')),
            management_approval text NOT NULL DEFAULT 'none' CHECK (management_approval IN
                ('none', 'sent_for_approval', 'approved_by_management')),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, kind, framework_key),
            FOREIGN KEY (tenant_id, checklist_template_version_id)
                REFERENCES disclosure_checklist_template_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statement_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            statement_document_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            source_snapshot_id uuid NOT NULL,
            adjustments_hash text NOT NULL CHECK (adjustments_hash {_SHA}),
            drafted_by_kind text NOT NULL CHECK (drafted_by_kind IN ('system', 'human')),
            run_id uuid NULL,
            initiator_user_id uuid NOT NULL,
            engine_version text NOT NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, statement_document_id, version_no),
            CHECK (drafted_by_kind <> 'system' OR run_id IS NOT NULL),
            FOREIGN KEY (tenant_id, statement_document_id)
                REFERENCES statement_documents (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        """
        CREATE TABLE line_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            statement_version_id uuid NOT NULL,
            statement_key text NOT NULL CHECK (statement_key ~ '^[a-z][a-z0-9_]{0,59}$'),
            section_key text NOT NULL CHECK (section_key ~ '^[a-z][a-z0-9_]{0,59}$'),
            line_key text NOT NULL CHECK (line_key ~ '^[a-z][a-z0-9_.]{0,79}$'),
            label text NOT NULL CHECK (char_length(btrim(label)) BETWEEN 1 AND 300),
            position integer NOT NULL CHECK (position >= 0),
            note_ref text NULL CHECK (char_length(note_ref) <= 40),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, statement_version_id, statement_key, line_key),
            FOREIGN KEY (tenant_id, statement_version_id)
                REFERENCES statement_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE linked_values (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            line_item_id uuid NOT NULL,
            year integer NOT NULL CHECK (year BETWEEN 1990 AND 2100),
            value numeric(20,2) NOT NULL,
            source text NOT NULL
                CHECK (source IN ('tb_linked', 'formula', 'override', 'stale_override')),
            source_ref jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(source_ref) = 'object'),
            citation_ids uuid[] NOT NULL DEFAULT '{}' CHECK (cardinality(citation_ids) <= 50),
            override_reason text NULL CHECK (char_length(override_reason) <= 2000),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, line_item_id, year),
            CONSTRAINT linked_values_override_reason CHECK (
                source NOT IN ('override', 'stale_override')
                OR (override_reason IS NOT NULL AND char_length(btrim(override_reason)) > 0)
            ),
            FOREIGN KEY (tenant_id, line_item_id) REFERENCES line_items (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tie_out_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            statement_version_id uuid NOT NULL,
            engine_version text NOT NULL,
            inputs_hash text NOT NULL CHECK (inputs_hash {_SHA}),
            total integer NOT NULL CHECK (total >= 0),
            tied integer NOT NULL CHECK (tied >= 0),
            off jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(off) = 'array'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (tied <= total),
            FOREIGN KEY (tenant_id, statement_version_id)
                REFERENCES statement_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE disclosure_checklist_answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            statement_document_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            item_key text NOT NULL CHECK (item_key ~ '^[a-z0-9][a-z0-9_.-]{{0,79}}$'),
            answer text NULL CHECK (answer IN ('yes', 'no', 'na')),
            note_ref text NULL CHECK (char_length(note_ref) <= 40),
            reason text NULL CHECK (char_length(reason) <= 2000),
            state text NOT NULL DEFAULT 'empty'
                CHECK (state IN ('empty', 'suggested', 'adopted', 'answered', 'reviewed')),
            suggestion_id uuid NULL,
            answered_by uuid NULL,
            adopted_by uuid NULL,
            reviewed_by uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, statement_document_id, item_key),
            CONSTRAINT disclosure_checklist_answers_na_reason CHECK (
                answer IS DISTINCT FROM 'na'
                OR (reason IS NOT NULL AND char_length(btrim(reason)) > 0)
            ),
            CHECK (state <> 'reviewed' OR reviewed_by IS NOT NULL),
            CHECK (state NOT IN ('answered', 'reviewed') OR answer IS NOT NULL),
            FOREIGN KEY (tenant_id, statement_document_id)
                REFERENCES statement_documents (tenant_id, id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES disclosure_checklist_template_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE statement_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            statement_version_id uuid NOT NULL,
            event text NOT NULL
                CHECK (event IN ('sent_for_approval', 'approved_by_management', 'commented')),
            actor_principal text NOT NULL CHECK (actor_principal IN ('firm_user', 'contact')),
            {_HUMAN},
            channel text NOT NULL CHECK (channel IN ('portal', 'record')),
            approval_item_ref text NULL CHECK (char_length(approval_item_ref) <= 200),
            deliverable_ref text NULL CHECK (char_length(deliverable_ref) <= 200),
            evidence_version_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (channel <> 'record' OR event <> 'approved_by_management'
                OR evidence_version_id IS NOT NULL),
            FOREIGN KEY (tenant_id, statement_version_id)
                REFERENCES statement_versions (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table in _INSERT_ONLY:
        insert_only(op, table)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    op.execute("REVOKE UPDATE ON disclosure_checklist_templates FROM abacus_app")
    op.execute(_IMMUTABLE)
    op.execute("REVOKE ALL ON FUNCTION statement_rows_immutable() FROM PUBLIC")
    for table in _INSERT_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION statement_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION statement_rows_immutable()"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION statement_rows_immutable()")
