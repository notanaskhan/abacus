"""Retention floors, default policies and firm policies (Q-02-T23; Q-02 §4.2, DEC-76 / P-62).

No floor, default or year count is written here: they are content, imported by platform staff
and published by a second one (AGENTS 16; Q-02 AC-30).

- `retention_floors` (global): the legal minimum per record type and service line (`any` for
  every line), its anchor event and authority, in numbered sets. A set is imported as `draft`
  and published only when a different staff member approves it (`approved_by <> imported_by`);
  publishing supersedes the previous published set.
- `retention_policy_defaults` (global): the default firm policy set, the same shape and the
  same two-person publish.
- `retention_policies` (tenant, forced RLS): a firm's years per record type and service line,
  the clock-start event, a lock and a basis. A trigger refuses years below the published floor
  (`below_floor`) and, while locked, any shortening (`policy_locked`). Every change is copied to
  the insert-only `retention_policy_versions`.

The app has no grant on the global tables. Definers:
- `retention_set_import(kind, version, rows, staff)` and `retention_set_publish(kind, version,
  staff)`: the staff routes' writers (`kind` is `floors` or `defaults`).
- `retention_floors_published()`: what any firm reads of the published floors.
- `retention_apply_defaults()`: the transaction's firm gets a policy per published default it
  lacks, never below its floor (provisioning calls it).
- `retention_defaults_backfill(operator)` (`abacus_ops` only): the one-off back-fill. It applies
  the defaults to every firm the platform created (provisioned or signed up), each under its own
  tenant setting with one `retention_policy.defaults_applied` event as the operator.

Revision ID: 0112
Revises: 0111
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None

_ANCHORS = (
    "('upload', 'report_release', 'filing_date', 'due_or_received_later', 'relationship_end', "
    "'client_inactive', 'message_date', 'event_date', 'period_end')"
)
_LINES = "('audit', 'tax', 'cas', 'advisory', 'any')"
_RECORD_TYPE = "~ '^[a-z][a-z0-9_]{1,62}$'"
_YEARS = "numeric(4, 1) NOT NULL CHECK ({c} > 0)"
_SET_STATUS = (
    "text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'superseded'))"
)
_STAFF = "text NOT NULL CHECK (char_length({c}) BETWEEN 1 AND 200)"
_FUNCTIONS = (
    "retention_set_import(text, integer, jsonb, text)",
    "retention_set_publish(text, integer, text)",
    "retention_floors_published()",
    "retention_apply_defaults()",
    # Trigger functions run only as triggers, and the floor lookup returns published floors, so
    # the app may hold EXECUTE on them (schema_check reviews every definer the same way).
    "retention_floor_of(text, text)",
    "retention_policy_guard()",
    "retention_policy_history()",
)


def _set_table(name: str, years: str, extra: str) -> str:
    return f"""
        CREATE TABLE {name} (
            set_version integer NOT NULL CHECK (set_version >= 1),
            record_type text NOT NULL CHECK (record_type {_RECORD_TYPE}),
            service_line text NOT NULL CHECK (service_line IN {_LINES}),
            {years} {_YEARS.format(c=years)},
            {extra}
            status {_SET_STATUS},
            imported_by {_STAFF.format(c="imported_by")},
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            approved_by text NULL CHECK (approved_by <> imported_by),
            published_at timestamptz NULL,
            CHECK ((status = 'draft') = (approved_by IS NULL)),
            PRIMARY KEY (set_version, record_type, service_line)
        )
    """


def upgrade() -> None:
    op.execute(
        _set_table(
            "retention_floors",
            "legal_floor_years",
            f"anchor text NOT NULL CHECK (anchor IN {_ANCHORS}),\n"
            "            authority text NOT NULL "
            "CHECK (char_length(authority) BETWEEN 1 AND 500),",
        )
    )
    op.execute(
        _set_table(
            "retention_policy_defaults",
            "firm_years",
            f"clock_start_event text NOT NULL CHECK (clock_start_event IN {_ANCHORS}),\n"
            "            lock boolean NOT NULL DEFAULT false,\n"
            "            basis text NULL CHECK (char_length(basis) BETWEEN 1 AND 500),",
        )
    )
    for table in ("retention_floors", "retention_policy_defaults"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute(
        f"""
        CREATE TABLE retention_policies (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            record_type text NOT NULL CHECK (record_type {_RECORD_TYPE}),
            service_line text NOT NULL CHECK (service_line IN {_LINES}),
            firm_years {_YEARS.format(c="firm_years")},
            clock_start_event text NOT NULL CHECK (clock_start_event IN {_ANCHORS}),
            lock boolean NOT NULL DEFAULT false,
            basis text NULL CHECK (char_length(basis) BETWEEN 1 AND 500),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by text NOT NULL CHECK (char_length(updated_by) BETWEEN 1 AND 200),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, record_type, service_line)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE retention_policy_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            record_type text NOT NULL,
            service_line text NOT NULL,
            version integer NOT NULL,
            firm_years numeric(4, 1) NOT NULL,
            clock_start_event text NOT NULL CHECK (clock_start_event IN {_ANCHORS}),
            lock boolean NOT NULL,
            basis text NULL,
            changed_by text NOT NULL,
            changed_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, record_type, service_line, version)
        )
        """
    )
    for table in ("retention_policies", "retention_policy_versions"):
        tenant_table(op, table)
    op.execute("REVOKE DELETE ON retention_policies FROM abacus_app")
    insert_columns(
        op,
        "retention_policies",
        (
            "tenant_id",
            "record_type",
            "service_line",
            "firm_years",
            "clock_start_event",
            "lock",
            "basis",
            "updated_by",
        ),
    )
    op.execute("REVOKE UPDATE ON retention_policies FROM abacus_app")
    op.execute(
        "GRANT UPDATE (firm_years, clock_start_event, lock, basis, updated_by, updated_at) "
        "ON retention_policies TO abacus_app"
    )
    insert_only(op, "retention_policy_versions")
    op.execute("REVOKE INSERT ON retention_policy_versions FROM abacus_app")  # the trigger's

    op.execute(
        """
        CREATE FUNCTION retention_floor_of(p_record_type text, p_line text) RETURNS numeric
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.legal_floor_years FROM public.retention_floors f
             WHERE f.status = 'published' AND f.record_type = p_record_type
               AND f.service_line IN (p_line, 'any')
             ORDER BY (f.service_line = p_line) DESC LIMIT 1
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_policy_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_floor numeric := public.retention_floor_of(NEW.record_type, NEW.service_line);
        BEGIN
            IF v_floor IS NOT NULL AND NEW.firm_years < v_floor THEN
                RAISE EXCEPTION 'below_floor' USING ERRCODE = 'check_violation',
                    CONSTRAINT = 'retention_policies_below_floor';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.lock AND NEW.lock AND NEW.firm_years < OLD.firm_years THEN
                    RAISE EXCEPTION 'policy_locked' USING ERRCODE = 'check_violation',
                        CONSTRAINT = 'retention_policies_locked';
                END IF;
                NEW.version := OLD.version + 1;
                NEW.updated_at := abacus_now();
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_policy_history() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            INSERT INTO public.retention_policy_versions (tenant_id, record_type, service_line,
                version, firm_years, clock_start_event, lock, basis, changed_by)
            VALUES (NEW.tenant_id, NEW.record_type, NEW.service_line, NEW.version,
                NEW.firm_years, NEW.clock_start_event, NEW.lock, NEW.basis, NEW.updated_by);
            RETURN NULL;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER retention_policy_guard BEFORE INSERT OR UPDATE ON retention_policies "
        "FOR EACH ROW EXECUTE FUNCTION retention_policy_guard()"
    )
    op.execute(
        "CREATE TRIGGER retention_policy_history AFTER INSERT OR UPDATE ON retention_policies "
        "FOR EACH ROW EXECUTE FUNCTION retention_policy_history()"
    )

    op.execute(
        """
        CREATE FUNCTION retention_set_import(
            p_kind text, p_version integer, p_rows jsonb, p_staff text
        ) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_rows integer;
        BEGIN
            IF p_kind = 'floors' THEN
                IF EXISTS (SELECT 1 FROM public.retention_floors WHERE set_version = p_version)
                THEN
                    RAISE EXCEPTION 'set_exists' USING ERRCODE = 'unique_violation';
                END IF;
                INSERT INTO public.retention_floors (set_version, record_type, service_line,
                    legal_floor_years, anchor, authority, imported_by)
                SELECT p_version, r->>'record_type', r->>'service_line',
                       (r->>'legal_floor_years')::numeric, r->>'anchor', r->>'authority', p_staff
                  FROM jsonb_array_elements(p_rows) r;
            ELSIF p_kind = 'defaults' THEN
                IF EXISTS (SELECT 1 FROM public.retention_policy_defaults
                            WHERE set_version = p_version) THEN
                    RAISE EXCEPTION 'set_exists' USING ERRCODE = 'unique_violation';
                END IF;
                INSERT INTO public.retention_policy_defaults (set_version, record_type,
                    service_line, firm_years, clock_start_event, lock, basis, imported_by)
                SELECT p_version, r->>'record_type', r->>'service_line',
                       (r->>'firm_years')::numeric, r->>'clock_start_event',
                       coalesce((r->>'lock')::boolean, false), r->>'basis', p_staff
                  FROM jsonb_array_elements(p_rows) r;
            ELSE
                RAISE EXCEPTION 'unknown set kind' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_set_publish(p_kind text, p_version integer, p_staff text)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_rows integer;
        BEGIN
            IF p_kind = 'floors' THEN
                IF EXISTS (SELECT 1 FROM public.retention_floors
                            WHERE set_version = p_version AND imported_by = p_staff) THEN
                    RAISE EXCEPTION 'same_person' USING ERRCODE = 'insufficient_privilege';
                END IF;
                UPDATE public.retention_floors SET status = 'superseded'
                 WHERE status = 'published' AND set_version <> p_version
                   AND EXISTS (SELECT 1 FROM public.retention_floors d
                                WHERE d.set_version = p_version AND d.status = 'draft');
                UPDATE public.retention_floors SET status = 'published', approved_by = p_staff,
                       published_at = clock_timestamp()
                 WHERE set_version = p_version AND status = 'draft';
            ELSIF p_kind = 'defaults' THEN
                IF EXISTS (SELECT 1 FROM public.retention_policy_defaults
                            WHERE set_version = p_version AND imported_by = p_staff) THEN
                    RAISE EXCEPTION 'same_person' USING ERRCODE = 'insufficient_privilege';
                END IF;
                UPDATE public.retention_policy_defaults SET status = 'superseded'
                 WHERE status = 'published' AND set_version <> p_version
                   AND EXISTS (SELECT 1 FROM public.retention_policy_defaults d
                                WHERE d.set_version = p_version AND d.status = 'draft');
                UPDATE public.retention_policy_defaults SET status = 'published',
                       approved_by = p_staff, published_at = clock_timestamp()
                 WHERE set_version = p_version AND status = 'draft';
            ELSE
                RAISE EXCEPTION 'unknown set kind' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_floors_published()
        RETURNS TABLE (set_version integer, record_type text, service_line text,
                       legal_floor_years numeric, anchor text, authority text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT f.set_version, f.record_type, f.service_line, f.legal_floor_years, f.anchor,
                   f.authority
              FROM public.retention_floors f WHERE f.status = 'published'
             ORDER BY f.record_type, f.service_line
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_apply_defaults() RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_actor text := current_setting('app.actor_kind', true) || ':'
                            || current_setting('app.actor_id', true);
            v_rows integer;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant' USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO public.retention_policies (tenant_id, record_type, service_line,
                firm_years, clock_start_event, lock, basis, updated_by)
            SELECT v_tenant, d.record_type, d.service_line,
                   greatest(d.firm_years,
                            coalesce(public.retention_floor_of(d.record_type, d.service_line), 0)),
                   d.clock_start_event, d.lock, d.basis, v_actor
              FROM public.retention_policy_defaults d
             WHERE d.status = 'published'
            ON CONFLICT (tenant_id, record_type, service_line) DO NOTHING;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            RETURN v_rows;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION retention_defaults_backfill(p_operator text)
        RETURNS TABLE (tenant_id uuid, applied integer)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_tenant uuid;
            v_rows integer;
            v_actor text := 'operator:' || p_operator;
        BEGIN
            IF p_operator !~ '^[a-z][a-z0-9._-]{0,60}$' THEN
                RAISE EXCEPTION 'bad operator' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            FOR v_tenant IN
                SELECT r.tenant_id FROM public.firm_provisioning_requests r
                UNION SELECT c.used_tenant_id FROM public.signup_codes c
                       WHERE c.used_tenant_id IS NOT NULL
                ORDER BY 1
            LOOP
                PERFORM set_config('app.tenant_id', v_tenant::text, true);
                PERFORM set_config('app.actor_kind', 'system', true);
                PERFORM set_config('app.actor_id', v_actor, true);
                PERFORM set_config('app.on_behalf_of', '', true);
                v_rows := public.retention_apply_defaults();
                IF v_rows > 0 THEN
                    INSERT INTO public.audit_events (tenant_id, actor_kind, actor_id, action,
                        target_type, target_id, after_ref)
                    VALUES (v_tenant, 'system', v_actor, 'retention_policy.defaults_applied',
                        'firm', v_tenant::text, jsonb_build_object('rows', v_rows));
                END IF;
                tenant_id := v_tenant;
                applied := v_rows;
                RETURN NEXT;
            END LOOP;
            PERFORM set_config('app.tenant_id', '', true);
        END $$
        """
    )
    for signature in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")
    op.execute("REVOKE ALL ON FUNCTION retention_defaults_backfill(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION retention_defaults_backfill(text) TO abacus_ops")


def downgrade() -> None:
    op.execute("DROP FUNCTION retention_defaults_backfill(text)")
    op.execute("DROP TABLE retention_policy_versions")
    op.execute("DROP TABLE retention_policies")
    for signature in _FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE retention_policy_defaults")
    op.execute("DROP TABLE retention_floors")
