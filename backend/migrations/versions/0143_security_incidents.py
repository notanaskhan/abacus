"""The security incident register (Q-02-T33; Q-02 §4.2, AC-38, AC-39; OQ-5; ADR-097; DEC-290).

- `security_incidents` (tenant, forced RLS): one row per incident in a firm's register, `ref`
  `INC-<year>-NNN` per firm. A firm entry (`source = 'firm'`) is recorded by the session's own
  person (`created_by`, bound by the guard trigger). An Accrued entry (`source = 'accrued'`) is
  written by the system when platform staff propagate an Accrued-side incident (RB-27): it names
  Accrued's reference, when Accrued confirmed it and when the firm was given notice
  (`dpa_notice_at`, the DPA's 72-hour clock), and has no person.
- `notification_event` is generated: unencrypted data of 500 or more consumers. `ftc_notify_by`
  is written by the service (the discovery date in the firm's time zone plus 30 calendar days)
  and is not a generated column, because time-zone conversion is not immutable.
- Insert-only for the app in v1: G-02-T18 grants the status change with its decisions.
- An Accrued entry keeps `facts_sha256`, the fingerprint of the facts that wrote it: a repeat
  with the same facts is the same entry, a repeat with different facts is refused (DEC-290).
  Only the propagation actor (`system`, `incident_propagation`) may write one.
- `incident_propagations` (global, insert-only, no app privileges): the staff record of every
  propagation request (requested or refused, with the refusal) and of every run's end
  (completed, with the failed firms). Written through `record_incident_propagation` only from
  a session with no tenant (staff routes and the propagation's finishing step), and read through
  `incident_propagation_log`.

Revision ID: 0143
Revises: 0133
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0143"
down_revision = "0133"
branch_labels = None
depends_on = None

_REFUSALS = (
    "('firm_not_found', 'register_off', 'facts_changed', 'confirmed_out_of_order', "
    "'propagation_running', 'firm_count')"
)
_RECORD = (
    "record_incident_propagation(text, text, uuid, text, text, integer, integer, integer, "
    "uuid[], text)"
)
_LOG = "incident_propagation_log(text)"
_KINDS = (
    "('unauthorized_access', 'credential_attack', 'data_exposure', 'lost_device', "
    "'vendor_incident', 'other')"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE security_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            ref text NOT NULL CHECK (ref ~ '^INC-[0-9]{{4}}-[0-9]{{3,}}$'),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            event_kind text NOT NULL CHECK (event_kind IN {_KINDS}),
            discovered_at timestamptz NOT NULL,
            consumers_affected integer NULL CHECK (consumers_affected >= 0),
            unencrypted boolean NULL,
            notification_event boolean GENERATED ALWAYS AS (
                coalesce(unencrypted, false) AND coalesce(consumers_affected, 0) >= 500
            ) STORED,
            ftc_notify_by date NOT NULL,
            status text NOT NULL DEFAULT 'investigating'
                CHECK (status IN ('investigating', 'closed')),
            source text NOT NULL CHECK (source IN ('firm', 'accrued')),
            accrued_ref text NULL CHECK (accrued_ref ~ '^[A-Z0-9][A-Z0-9-]{{2,39}}$'),
            accrued_confirmed_at timestamptz NULL,
            dpa_notice_at timestamptz NULL,
            facts_sha256 text NULL CHECK (facts_sha256 ~ '^[0-9a-f]{{64}}$'),
            created_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, ref),
            UNIQUE (tenant_id, accrued_ref),
            CONSTRAINT security_incidents_source_shape CHECK (
                CASE source
                    WHEN 'firm' THEN created_by IS NOT NULL AND accrued_ref IS NULL
                        AND accrued_confirmed_at IS NULL AND dpa_notice_at IS NULL
                        AND facts_sha256 IS NULL
                    ELSE created_by IS NULL AND accrued_ref IS NOT NULL
                        AND accrued_confirmed_at IS NOT NULL AND dpa_notice_at IS NOT NULL
                        AND facts_sha256 IS NOT NULL
                END
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX security_incidents_open ON security_incidents (tenant_id, discovered_at) "
        "WHERE status = 'investigating'"
    )
    tenant_table(op, "security_incidents")
    insert_only(op, "security_incidents")
    op.execute("REVOKE TRUNCATE ON security_incidents FROM abacus_app")
    insert_columns(
        op,
        "security_incidents",
        (
            "id",
            "tenant_id",
            "ref",
            "title",
            "event_kind",
            "discovered_at",
            "consumers_affected",
            "unencrypted",
            "ftc_notify_by",
            "source",
            "accrued_ref",
            "accrued_confirmed_at",
            "dpa_notice_at",
            "facts_sha256",
            "created_by",
        ),
    )
    # A firm entry is the session's own person's; an Accrued entry is the platform's (system).
    op.execute(
        """
        CREATE FUNCTION security_incidents_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.source = 'firm' AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR NEW.created_by::text IS DISTINCT FROM current_setting('app.actor_id', true)
            ) THEN
                RAISE EXCEPTION 'a firm''s incident is recorded by the session''s own person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.source = 'accrued' AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM 'incident_propagation'
            ) THEN
                RAISE EXCEPTION 'an Accrued incident is propagated by the system'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_incidents_guard BEFORE INSERT ON security_incidents "
        "FOR EACH ROW EXECUTE FUNCTION security_incidents_guard()"
    )

    op.execute(
        f"""
        CREATE TABLE incident_propagations (
            id bigserial PRIMARY KEY,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            accrued_ref text NOT NULL CHECK (accrued_ref ~ '^[A-Z0-9][A-Z0-9-]{{2,39}}$'),
            event text NOT NULL CHECK (event IN ('requested', 'refused', 'completed')),
            staff_id uuid NOT NULL,
            reason_sha256 text NOT NULL CHECK (reason_sha256 ~ '^[0-9a-f]{{64}}$'),
            facts_sha256 text NULL CHECK (facts_sha256 ~ '^[0-9a-f]{{64}}$'),
            firms integer NOT NULL CHECK (firms >= 0),
            written integer NOT NULL DEFAULT 0 CHECK (written >= 0),
            identical integer NOT NULL DEFAULT 0 CHECK (identical >= 0),
            failed_tenant_ids uuid[] NOT NULL DEFAULT '{{}}',
            refusal text NULL CHECK (refusal IN {_REFUSALS}),
            CONSTRAINT incident_propagations_refusal CHECK (
                (event = 'refused') = (refusal IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX incident_propagations_by_ref ON incident_propagations (accrued_ref, id)"
    )
    op.execute(
        """
        CREATE FUNCTION incident_propagations_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'incident_propagations is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER incident_propagations_immutable BEFORE UPDATE OR DELETE "
        "ON incident_propagations FOR EACH ROW EXECUTE FUNCTION incident_propagations_immutable()"
    )
    op.execute("REVOKE ALL ON incident_propagations FROM abacus_app")
    op.execute("REVOKE ALL ON SEQUENCE incident_propagations_id_seq FROM abacus_app")
    # Written only from a session with no tenant: a staff route as `staff:<the staff id>`, or the
    # propagation's finishing step as `incident_propagation` (completed only). A firm's session
    # (any tenant set) can never write the platform's record.
    op.execute(
        """
        CREATE FUNCTION record_incident_propagation(
            p_ref text, p_event text, p_staff uuid, p_reason text, p_facts text,
            p_firms integer, p_written integer, p_identical integer, p_failed uuid[],
            p_refusal text
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_actor text := current_setting('app.actor_id', true);
            v_id bigint;
        BEGIN
            IF coalesce(current_setting('app.tenant_id', true), '') <> ''
               OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
               OR NOT (
                   v_actor = 'staff:' || p_staff::text
                   OR (p_event = 'completed' AND v_actor = 'incident_propagation')
               ) THEN
                RAISE EXCEPTION 'the propagation record is the platform''s'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO public.incident_propagations (accrued_ref, event, staff_id,
                reason_sha256, facts_sha256, firms, written, identical, failed_tenant_ids,
                refusal)
            VALUES (p_ref, p_event, p_staff, p_reason, p_facts, p_firms, p_written,
                p_identical, coalesce(p_failed, '{}'), p_refusal)
            RETURNING id INTO v_id;
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION incident_propagation_log(p_ref text)
        RETURNS TABLE (recorded_at timestamptz, event text, staff_id uuid, firms integer,
            written integer, identical integer, failed_tenant_ids uuid[], refusal text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            IF coalesce(current_setting('app.tenant_id', true), '') <> '' THEN
                RAISE EXCEPTION 'the propagation record is the platform''s'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN QUERY SELECT p.recorded_at, p.event, p.staff_id, p.firms, p.written,
                p.identical, p.failed_tenant_ids, p.refusal
              FROM public.incident_propagations p WHERE p.accrued_ref = p_ref ORDER BY p.id;
        END $$
        """
    )
    for function in (_RECORD, _LOG):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_LOG}")
    op.execute(f"DROP FUNCTION {_RECORD}")
    op.execute("DROP TABLE incident_propagations")
    op.execute("DROP FUNCTION incident_propagations_immutable()")
    op.execute("DROP TABLE security_incidents")
    op.execute("DROP FUNCTION security_incidents_guard()")
