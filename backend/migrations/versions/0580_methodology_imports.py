"""Methodology import review (K-01-T18; K-01 §4.2 migration C; DEC-1755). Expand-only.

Four `methodology` tables, every one tenant-scoped with forced RLS:

- `methodology_imports`: one upload of a firm's methodology files, from `awaiting_files` through
  `scanning` and `parsing` to `needs_review` (its version) or `failed` / `cancelled`. Created once
  per Idempotency-Key. The app may move only its status, version, progress and failure code.
- `methodology_source_files` (insert-only): one stored file per role (`document_docx`,
  `document_pdf`, `workbook`), written once to the evidence store under S3 Object Lock and
  scanned before it is kept; the storage key and object version are never serialised.
- `methodology_source_pages` (insert-only): a document file's page sizes and word boxes, for the
  viewer's highlight and the importer's quote verification (K-01-T20 fills them).
- `program_step_sources` (insert-only): where a step came from: the file, the page range, the
  region and the quote, with the code verification's result.

`standards_set_named(id)` (SECURITY DEFINER) lets the app read one platform standards set's code
and label by id, for KNW-02 d. `methodology_version_events.kind` gains `import_started` and
`flag_resolved`, and 0224's `methodology_content_frozen()` lets a version in review take one
update: a person resolving a step's open parse flag (its resolution columns, and the text for an
edit; nothing else).

Revision ID: 0580
Revises: 0524
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_only, tenant_table

revision = "0580"
down_revision = "0524"
branch_labels = None
depends_on = None

_KINDS = (
    "'legacy_backfilled', 'imported', 'published', 'draft_created', 'submitted', 'approved', "
    "'superseded', 'discarded', 'standards_mapped', 'exported', "
    "'step_added', 'step_edited', 'step_removed', 'mandatory_changed'"
)
# K-01-T18: an import's version records its start and each flag a person resolves.
_IMPORT_KINDS = "'import_started', 'flag_resolved'"


def _kinds(kinds: str) -> None:
    op.execute(
        "ALTER TABLE methodology_version_events "
        "DROP CONSTRAINT methodology_version_events_kind_check, "
        f"ADD CONSTRAINT methodology_version_events_kind_check CHECK (kind IN ({kinds}))"
    )


# 0224's frozen trigger, with one opening: resolving a parse flag in review (K-01-T18).
_FROZEN_0224 = """
    CREATE OR REPLACE FUNCTION methodology_content_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_tenant uuid;
        v_version uuid;
        v_status text;
    BEGIN
        -- The owner's maintenance (migrations) logs in as abacus_owner; a SECURITY DEFINER
        -- function owned by it still runs in the app's session, so `session_user`, not
        -- `current_user`, decides (security review L).
        IF session_user = 'abacus_owner' THEN
            RETURN COALESCE(NEW, OLD);
        END IF;
        IF TG_OP = 'DELETE' THEN
            v_tenant := OLD.tenant_id;
            v_version := OLD.version_id;
        ELSE
            v_tenant := NEW.tenant_id;
            v_version := NEW.version_id;
        END IF;
        IF TG_OP = 'UPDATE' AND (OLD.version_id IS DISTINCT FROM NEW.version_id
                                 OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id) THEN
            RAISE EXCEPTION 'a step stays in its version'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- Share-lock the version's state row: a publish (an UPDATE of that row) waits for this
        -- edit to commit, and an edit waits for a publish, so content never changes under an
        -- approval (security review M2).
        SELECT s.status INTO v_status FROM public.methodology_version_states s
         WHERE s.tenant_id = v_tenant AND s.version_id = v_version
         FOR SHARE;
        -- Only a draft (or one being parsed) changes; in review, published, superseded or
        -- discarded content is frozen. No state row yet: the import writing the version now.
        IF FOUND AND v_status NOT IN ('draft', 'parsing') THEN
            RAISE EXCEPTION 'a methodology version''s content is frozen once it leaves draft'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN COALESCE(NEW, OLD);
    END $$
"""
_FROZEN = """
    CREATE OR REPLACE FUNCTION methodology_content_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_tenant uuid;
        v_version uuid;
        v_status text;
    BEGIN
        -- The owner's maintenance (migrations) logs in as abacus_owner; a SECURITY DEFINER
        -- function owned by it still runs in the app's session, so `session_user`, not
        -- `current_user`, decides (security review L).
        IF session_user = 'abacus_owner' THEN
            RETURN COALESCE(NEW, OLD);
        END IF;
        IF TG_OP = 'DELETE' THEN
            v_tenant := OLD.tenant_id;
            v_version := OLD.version_id;
        ELSE
            v_tenant := NEW.tenant_id;
            v_version := NEW.version_id;
        END IF;
        IF TG_OP = 'UPDATE' AND (OLD.version_id IS DISTINCT FROM NEW.version_id
                                 OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id) THEN
            RAISE EXCEPTION 'a step stays in its version'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- Share-lock the version's state row: a publish (an UPDATE of that row) waits for this
        -- edit to commit, and an edit waits for a publish, so content never changes under an
        -- approval (security review M2).
        SELECT s.status INTO v_status FROM public.methodology_version_states s
         WHERE s.tenant_id = v_tenant AND s.version_id = v_version
         FOR SHARE;
        -- Only a draft (or one being parsed) changes; in review, published, superseded or
        -- discarded content is frozen. No state row yet: the import writing the version now.
        -- K-01-T18 (0580): in review, a person resolves a step's open parse flag: confirm it,
        -- or edit the text, the step keeping its key, origin and source. Nothing else moves.
        IF FOUND AND v_status = 'needs_review' AND TG_TABLE_NAME = 'program_steps'
           AND TG_OP = 'UPDATE'
           AND OLD.parse_flag IS NOT NULL AND OLD.flag_resolution IS NULL
           AND NEW.flag_resolution IS NOT NULL
           AND (to_jsonb(NEW) - ARRAY['text', 'flag_resolution', 'flag_resolved_by',
                                      'flag_resolved_at', 'edited_by', 'edited_at',
                                      'row_version'])
             = (to_jsonb(OLD) - ARRAY['text', 'flag_resolution', 'flag_resolved_by',
                                      'flag_resolved_at', 'edited_by', 'edited_at',
                                      'row_version']) THEN
            RETURN NEW;
        END IF;
        IF FOUND AND v_status NOT IN ('draft', 'parsing') THEN
            RAISE EXCEPTION 'a methodology version''s content is frozen once it leaves draft'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN COALESCE(NEW, OLD);
    END $$
"""


_TABLES = (
    "program_step_sources",
    "methodology_source_pages",
    "methodology_source_files",
    "methodology_imports",
)


_STANDARDS_SET = """
    CREATE FUNCTION standards_set_named(p_id uuid)
    RETURNS TABLE (id uuid, code text, label text, family text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        SELECT s.id, s.code, s.label, s.family FROM public.standards_sets s WHERE s.id = p_id
    $$
"""


def upgrade() -> None:
    _kinds(f"{_KINDS}, {_IMPORT_KINDS}")
    op.execute(_FROZEN)
    # KNW-02 d names the mapped set: platform reference rows, readable one by id (no tenant data).
    op.execute(_STANDARDS_SET)
    op.execute("REVOKE ALL ON FUNCTION standards_set_named(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION standards_set_named(uuid) TO abacus_app")
    op.execute(
        """
        CREATE TABLE methodology_imports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version_id uuid NULL,
            status text NOT NULL DEFAULT 'awaiting_files' CHECK (status IN ('awaiting_files',
                'scanning', 'parsing', 'needs_review', 'failed', 'cancelled')),
            started_by uuid NOT NULL,
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            agent_run_id uuid NULL,
            pages_done integer NOT NULL DEFAULT 0 CHECK (pages_done >= 0),
            pages_total integer NULL CHECK (pages_total IS NULL OR pages_total >= 0),
            failure_code text NULL CHECK (failure_code IS NULL
                OR failure_code ~ '^[a-z][a-z0-9_]{0,63}$'),
            idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, idempotency_key),
            CHECK (pages_total IS NULL OR pages_done <= pages_total),
            CHECK ((status = 'failed') = (failure_code IS NOT NULL)),
            CHECK (status <> 'needs_review' OR version_id IS NOT NULL),
            FOREIGN KEY (tenant_id, template_id) REFERENCES methodology_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_source_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            import_id uuid NOT NULL,
            version_id uuid NULL,
            role text NOT NULL CHECK (role IN ('document_docx', 'document_pdf', 'workbook')),
            rendition_of_file_id uuid NULL,
            filename text NOT NULL CHECK (char_length(filename) BETWEEN 1 AND 255),
            media_type text NOT NULL CHECK (char_length(media_type) BETWEEN 1 AND 127),
            storage_key text NOT NULL CHECK (char_length(storage_key) BETWEEN 1 AND 1024),
            storage_version_id text NOT NULL CHECK (char_length(storage_version_id) BETWEEN 1
                AND 1024),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            bytes bigint NOT NULL CHECK (bytes > 0),
            page_count integer NULL CHECK (page_count IS NULL OR page_count >= 0),
            sheet_count integer NULL CHECK (sheet_count IS NULL OR sheet_count >= 0),
            scan_status text NOT NULL CHECK (scan_status IN ('clean')),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, import_id, role),
            FOREIGN KEY (tenant_id, import_id) REFERENCES methodology_imports (tenant_id, id),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, rendition_of_file_id)
                REFERENCES methodology_source_files (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_source_pages (
            tenant_id uuid NOT NULL,
            file_id uuid NOT NULL,
            page integer NOT NULL CHECK (page >= 1),
            width numeric(8, 2) NOT NULL CHECK (width > 0),
            height numeric(8, 2) NOT NULL CHECK (height > 0),
            words jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(words) = 'array'),
            PRIMARY KEY (tenant_id, file_id, page),
            FOREIGN KEY (tenant_id, file_id) REFERENCES methodology_source_files (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE program_step_sources (
            tenant_id uuid NOT NULL,
            step_id uuid NOT NULL,
            source_file_id uuid NOT NULL,
            page_from integer NOT NULL CHECK (page_from >= 1),
            page_to integer NOT NULL CHECK (page_to >= page_from),
            bbox jsonb NULL CHECK (bbox IS NULL OR jsonb_typeof(bbox) = 'array'),
            quote text NULL CHECK (char_length(quote) <= 4000),
            verified boolean NOT NULL,
            verify_reason text NULL CHECK (verify_reason IS NULL
                OR verify_reason ~ '^[a-z][a-z0-9_]{0,63}$'),
            verified_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, step_id, source_file_id, page_from),
            CHECK (verified OR verify_reason IS NOT NULL),
            FOREIGN KEY (tenant_id, step_id) REFERENCES program_steps (tenant_id, id),
            FOREIGN KEY (tenant_id, source_file_id)
                REFERENCES methodology_source_files (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX methodology_source_files_version ON methodology_source_files "
        "(tenant_id, version_id)"
    )
    op.execute(
        "CREATE INDEX methodology_imports_version ON methodology_imports (tenant_id, version_id)"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in ("methodology_source_files", "methodology_source_pages", "program_step_sources"):
        insert_only(op, table)
    op.execute("REVOKE UPDATE ON methodology_imports FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, version_id, agent_run_id, pages_done, pages_total, failure_code) "
        "ON methodology_imports TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION standards_set_named(uuid)")
    op.execute(_FROZEN_0224)
    _kinds(_KINDS)
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
