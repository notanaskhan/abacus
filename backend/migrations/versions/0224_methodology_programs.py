"""K-01-T05: a methodology version's programs and steps (K-01 §4.2 migration B; TASK-1427).

- `programs` (new, forced RLS): a version's programs (`BH-EBP-110` General Planning), by code
  and position.
- `program_steps` (new, forced RLS): each program's numbered steps with a stable `step_key`
  (the lineage anchor: identical across versions for an unchanged or changed step, so citations
  `step_key@v<n>` survive renumbering), text, assertions, standards references, level
  (Foundation, Planning, Testing, Completion), the mandatory lock and its note (code, from the
  workbook's columns only), sanitised guidance blocks, prepopulation targets and dependencies,
  and the parse facts the document importer (K-01-T18) fills. Step numbers are unique per program
  (deferrable, so a draft's renumbering commits whole).
- `program_step_pbc_links` (new, forced RLS, insert-only): a step's links to the version's PBC
  request items, by position.
- `methodology_content_frozen()` on all three: once the version is `published` or `superseded`,
  no row of it is inserted, updated or deleted, by anyone but the owner's maintenance. Content is
  changed in a new draft (K-01-T14). SECURITY INVOKER with a pinned search path: it reads the
  version's state under the caller's own row-level security.

Every column is set at insert; the app may later edit a draft step's content columns (K-01-T14)
and delete a draft's step, which the trigger refuses on a published version. No content is
inserted here (rule 16): programs arrive through the workbook import.

Revision ID: 0224
Revises: 0223
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0224"
down_revision = "0223"
branch_labels = None
depends_on = None

_KEY = "'^[a-z0-9][a-z0-9_.-]{0,79}$'"
_STEP_EDITS = (
    "number",
    "text",
    "assertions",
    "standard_refs",
    "level",
    "guidance",
    "prepopulates",
    "depends_on_step_keys",
    "flag_resolution",
    "flag_resolved_by",
    "flag_resolved_at",
    "edited_by",
    "edited_at",
    "row_version",
)

_FROZEN = """
    CREATE FUNCTION methodology_content_frozen() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        v_tenant uuid;
        v_version uuid;
    BEGIN
        IF current_user = 'abacus_owner' THEN
            RETURN COALESCE(NEW, OLD);  -- the owner's maintenance (migrations), not the app
        END IF;
        IF TG_OP = 'DELETE' THEN
            v_tenant := OLD.tenant_id;
            v_version := OLD.version_id;
        ELSE
            v_tenant := NEW.tenant_id;
            v_version := NEW.version_id;
        END IF;
        IF EXISTS (
            SELECT 1 FROM public.methodology_version_states s
             WHERE s.tenant_id = v_tenant AND s.version_id = v_version
               AND s.status IN ('published', 'superseded')
        ) OR (TG_OP = 'UPDATE' AND (OLD.version_id IS DISTINCT FROM NEW.version_id
                                    OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id)) THEN
            RAISE EXCEPTION 'a published methodology version''s content is frozen'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN COALESCE(NEW, OLD);
    END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE programs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            code text NOT NULL CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$'),
            name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
            position integer NOT NULL CHECK (position >= 0),
            publisher_program_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, id),
            CONSTRAINT programs_one_code UNIQUE (tenant_id, version_id, code),
            CONSTRAINT programs_one_position UNIQUE (tenant_id, version_id, position),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE program_steps (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            program_id uuid NOT NULL,
            step_key text NOT NULL CHECK (step_key ~ {_KEY}),
            number integer NOT NULL CHECK (number BETWEEN 1 AND 9999),
            text text NOT NULL CHECK (length(btrim(text)) BETWEEN 1 AND 4000),
            assertions text[] NOT NULL DEFAULT '{{}}',
            standard_refs text[] NOT NULL DEFAULT '{{}}',
            level text NOT NULL
                CHECK (level IN ('foundation', 'planning', 'testing', 'completion')),
            mandatory boolean NOT NULL DEFAULT false,
            lock_note text NULL CHECK (length(btrim(lock_note)) BETWEEN 1 AND 200),
            guidance jsonb NULL CHECK (guidance IS NULL OR jsonb_typeof(guidance) = 'array'),
            prepopulates text[] NOT NULL DEFAULT '{{}}',
            depends_on_step_keys text[] NOT NULL DEFAULT '{{}}',
            publisher_step_id uuid NULL,
            origin text NOT NULL CHECK (origin IN ('workbook', 'importer', 'manual')),
            proposed_by_run_id uuid NULL,
            parse_confidence numeric(4, 3) NULL
                CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),
            parse_flag text NULL CHECK (parse_flag IN ('low_confidence', 'split_across_pages',
                'numbering_gap', 'unverified_citation', 'cross_reference_missing')),
            flag_resolution text NULL CHECK (flag_resolution IN ('confirmed', 'edited')),
            flag_resolved_by uuid NULL,
            flag_resolved_at timestamptz NULL,
            edited_by uuid NULL,
            edited_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, id),
            CONSTRAINT program_steps_one_key UNIQUE (tenant_id, version_id, step_key),
            CONSTRAINT program_steps_one_number UNIQUE (tenant_id, program_id, number)
                DEFERRABLE INITIALLY IMMEDIATE,
            -- The lock note says why a step is locked; an unlocked step has none.
            CONSTRAINT program_steps_lock_note CHECK (lock_note IS NULL OR mandatory),
            CONSTRAINT program_steps_resolved CHECK (
                (flag_resolution IS NULL) = (flag_resolved_by IS NULL)
                AND (flag_resolution IS NULL) = (flag_resolved_at IS NULL)
                AND (flag_resolution IS NULL OR parse_flag IS NOT NULL)
            ),
            FOREIGN KEY (tenant_id, version_id, program_id)
                REFERENCES programs (tenant_id, version_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX program_steps_program ON program_steps (tenant_id, program_id, number)"
    )
    op.execute(
        """
        CREATE TABLE program_step_pbc_links (
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            step_id uuid NOT NULL,
            request_position integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, step_id, request_position),
            FOREIGN KEY (tenant_id, version_id, step_id)
                REFERENCES program_steps (tenant_id, version_id, id),
            FOREIGN KEY (tenant_id, version_id, request_position)
                REFERENCES methodology_request_items (tenant_id, version_id, position)
        )
        """
    )
    for table in ("programs", "program_steps", "program_step_pbc_links"):
        tenant_table(op, table)
    insert_columns(
        op,
        "programs",
        ("tenant_id", "version_id", "code", "name", "position", "publisher_program_id"),
    )
    op.execute("REVOKE UPDATE, DELETE ON programs FROM abacus_app")
    insert_columns(
        op,
        "program_steps",
        (
            "id",
            "tenant_id",
            "version_id",
            "program_id",
            "step_key",
            "number",
            "text",
            "assertions",
            "standard_refs",
            "level",
            "mandatory",
            "lock_note",
            "guidance",
            "prepopulates",
            "depends_on_step_keys",
            "publisher_step_id",
            "origin",
            "proposed_by_run_id",
            "parse_confidence",
            "parse_flag",
        ),
    )
    # K-01-T14 edits a draft's step content and removes a draft's step; the frozen trigger
    # refuses both on a published or superseded version. `mandatory` and `lock_note` are not
    # here: the lock is its own human-only act (K-01-T14, `methodology.approve`).
    op.execute("REVOKE UPDATE ON program_steps FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_STEP_EDITS)}) ON program_steps TO abacus_app")
    insert_only(op, "program_step_pbc_links")
    insert_columns(
        op, "program_step_pbc_links", ("tenant_id", "version_id", "step_id", "request_position")
    )
    op.execute(_FROZEN)
    for table in ("programs", "program_steps", "program_step_pbc_links"):
        op.execute(
            f"CREATE TRIGGER {table}_frozen BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION methodology_content_frozen()"
        )


def downgrade() -> None:
    op.execute("DROP TABLE program_step_pbc_links")
    op.execute("DROP TABLE program_steps")
    op.execute("DROP TABLE programs")
    op.execute("DROP FUNCTION methodology_content_frozen()")
