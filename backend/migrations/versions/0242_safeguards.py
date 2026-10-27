"""The safeguards program (G-02-T20; SPEC-349 AC-27, AC-30; DEC-626, DEC-627).

- `safeguards_controls` (global, no app privileges): the Pub 4557 control definitions, platform
  content imported by staff as a numbered draft set and published by a second staff member
  (the retention-set pattern of 0112). Nothing here or in the code holds a control.
  `safeguards_controls_import`, `safeguards_controls_publish` (staff routes only) and
  `safeguards_controls_published()` (any firm reads the published set) are its definers.
- `safeguards_programs` (tenant PK, forced RLS): the firm's record (QI, WISP and its approval,
  annual report dates, training, PTIN attestation, the quarterly access review), edited in place
  against `version` by a live person (the trigger); never deleted.
- `safeguards_control_statuses` (tenant, forced RLS): one row per control the firm has a status
  for (`evidenced` or `open`); a control with no row counts as open.
- `wisp_packs` (tenant, forced RLS): Export WISP pack jobs, asked for by a person and completed
  by the system; never deleted by the app.

Revision ID: 0242
Revises: 0241
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0242"
down_revision = "0241"
branch_labels = None
depends_on = None

_KEY = "~ '^[a-z0-9][a-z0-9_.-]{0,63}$'"
_FUNCTIONS = (
    "safeguards_controls_import(integer, jsonb, text)",
    "safeguards_controls_publish(integer, text)",
    "safeguards_controls_published()",
)
_PROGRAM_COLUMNS = (
    "qi_user_id",
    "wisp_name",
    "wisp_evidence_item_id",
    "wisp_approved_by",
    "wisp_approved_on",
    "annual_report_last_on",
    "annual_report_next_due_month",
    "access_review_quarter",
    "access_review_due_on",
    "access_review_status",
    "training_completed",
    "ptin_attested",
    "ptin_total",
    "updated_by",
)
_CONTROL_COLUMNS = (
    "status",
    "due_on",
    "scheduled_on",
    "evidence_item_id",
    "note",
    "updated_by",
)


def _actor_guard(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_actor() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.updated_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a safeguards record is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_actor BEFORE INSERT OR UPDATE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_actor()"
    )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE safeguards_controls (
            set_version integer NOT NULL CHECK (set_version >= 1),
            control_key text NOT NULL CHECK (control_key {_KEY}),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            position smallint NOT NULL CHECK (position >= 1),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'superseded')),
            imported_by text NOT NULL CHECK (char_length(imported_by) BETWEEN 1 AND 200),
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            approved_by text NULL CHECK (approved_by <> imported_by),
            published_at timestamptz NULL,
            CHECK ((status = 'draft') = (approved_by IS NULL)),
            PRIMARY KEY (set_version, control_key),
            UNIQUE (set_version, position)
        )
        """
    )
    op.execute("REVOKE ALL ON safeguards_controls FROM abacus_app")
    op.execute(
        """
        CREATE FUNCTION safeguards_controls_import(p_version integer, p_rows jsonb, p_staff text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_rows integer;
        BEGIN
            IF current_setting('app.tenant_id', true) IS NOT NULL
               AND current_setting('app.tenant_id', true) <> '' THEN
                RAISE EXCEPTION 'platform content is imported outside a firm'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF EXISTS (SELECT 1 FROM public.safeguards_controls WHERE set_version = p_version) THEN
                RAISE EXCEPTION 'set_exists' USING ERRCODE = 'unique_violation';
            END IF;
            INSERT INTO public.safeguards_controls (set_version, control_key, title, position,
                imported_by)
            SELECT p_version, r->>'control_key', r->>'title', (r->>'position')::smallint, p_staff
              FROM jsonb_array_elements(p_rows) r;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION safeguards_controls_publish(p_version integer, p_staff text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_rows integer;
        BEGIN
            IF current_setting('app.tenant_id', true) IS NOT NULL
               AND current_setting('app.tenant_id', true) <> '' THEN
                RAISE EXCEPTION 'platform content is published outside a firm'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF EXISTS (SELECT 1 FROM public.safeguards_controls
                        WHERE set_version = p_version AND imported_by = p_staff) THEN
                RAISE EXCEPTION 'same_person' USING ERRCODE = 'insufficient_privilege';
            END IF;
            UPDATE public.safeguards_controls SET status = 'superseded'
             WHERE status = 'published' AND set_version <> p_version
               AND EXISTS (SELECT 1 FROM public.safeguards_controls d
                            WHERE d.set_version = p_version AND d.status = 'draft');
            UPDATE public.safeguards_controls SET status = 'published', approved_by = p_staff,
                   published_at = clock_timestamp()
             WHERE set_version = p_version AND status = 'draft';
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION safeguards_controls_published()
        RETURNS TABLE (control_key text, title text, "position" smallint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT c.control_key, c.title, c.position FROM public.safeguards_controls c
             WHERE c.status = 'published' ORDER BY c.position
        $$
        """
    )
    for signature in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")

    op.execute(
        """
        CREATE TABLE safeguards_programs (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            qi_user_id uuid NULL,
            wisp_name text NULL CHECK (char_length(wisp_name) BETWEEN 1 AND 200),
            wisp_evidence_item_id uuid NULL,
            wisp_approved_by uuid NULL,
            wisp_approved_on date NULL,
            annual_report_last_on date NULL,
            annual_report_next_due_month text NULL
                CHECK (annual_report_next_due_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
            access_review_quarter text NULL CHECK (access_review_quarter ~ '^[0-9]{4}-Q[1-4]$'),
            access_review_due_on date NULL,
            access_review_status text NULL
                CHECK (access_review_status IN ('not_started', 'in_progress', 'complete')),
            training_completed integer NULL CHECK (training_completed >= 0),
            ptin_attested integer NULL CHECK (ptin_attested >= 0),
            ptin_total integer NULL CHECK (ptin_total >= 0),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (ptin_attested IS NULL OR ptin_total IS NULL OR ptin_attested <= ptin_total),
            CHECK ((access_review_quarter IS NULL) = (access_review_due_on IS NULL))
        )
        """
    )
    tenant_table(op, "safeguards_programs")
    insert_columns(op, "safeguards_programs", ("tenant_id", *_PROGRAM_COLUMNS))
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON safeguards_programs FROM abacus_app")
    op.execute(
        f"GRANT UPDATE ({', '.join((*_PROGRAM_COLUMNS, 'version', 'updated_at'))}) "
        "ON safeguards_programs TO abacus_app"
    )
    _actor_guard("safeguards_programs")

    op.execute(
        f"""
        CREATE TABLE safeguards_control_statuses (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            control_key text NOT NULL CHECK (control_key {_KEY}),
            status text NOT NULL CHECK (status IN ('evidenced', 'open')),
            due_on date NULL,
            scheduled_on date NULL,
            evidence_item_id uuid NULL,
            note text NULL CHECK (char_length(note) BETWEEN 1 AND 500),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, control_key)
        )
        """
    )
    tenant_table(op, "safeguards_control_statuses")
    insert_columns(op, "safeguards_control_statuses", ("tenant_id", "control_key", *_CONTROL_COLUMNS))
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON safeguards_control_statuses FROM abacus_app")
    op.execute(
        f"GRANT UPDATE ({', '.join((*_CONTROL_COLUMNS, 'updated_at'))}) "
        "ON safeguards_control_statuses TO abacus_app"
    )
    _actor_guard("safeguards_control_statuses")

    op.execute(
        """
        CREATE TABLE wisp_packs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            requested_by uuid NOT NULL,
            status text NOT NULL DEFAULT 'preparing'
                CHECK (status IN ('preparing', 'ready', 'failed')),
            document_count integer NULL CHECK (document_count >= 0),
            segment_count integer NULL CHECK (segment_count >= 0),
            bundle_bytes bigint NULL CHECK (bundle_bytes >= 0),
            failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{1,63}$'),
            expires_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute("CREATE INDEX wisp_packs_firm ON wisp_packs (tenant_id, created_at DESC)")
    tenant_table(op, "wisp_packs")
    insert_columns(op, "wisp_packs", ("id", "tenant_id", "requested_by"))
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON wisp_packs FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, document_count, segment_count, bundle_bytes, failure_code, "
        "expires_at, updated_at) ON wisp_packs TO abacus_app"
    )
    # Asked for by the session's own person; completed (once) by the system.
    op.execute(
        """
        CREATE FUNCTION wisp_packs_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                   OR NEW.requested_by::text
                      IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                    RAISE EXCEPTION 'a WISP pack is asked for by the session''s own person'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
                  OR OLD.status <> 'preparing' THEN
                RAISE EXCEPTION 'a WISP pack is completed once, by the system'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER wisp_packs_guard BEFORE INSERT OR UPDATE ON wisp_packs "
        "FOR EACH ROW EXECUTE FUNCTION wisp_packs_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE wisp_packs")
    op.execute("DROP FUNCTION wisp_packs_guard()")
    op.execute("DROP TABLE safeguards_control_statuses")
    op.execute("DROP FUNCTION safeguards_control_statuses_actor()")
    op.execute("DROP TABLE safeguards_programs")
    op.execute("DROP FUNCTION safeguards_programs_actor()")
    for signature in _FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE safeguards_controls")
