"""The incident register's depth on Q-02's kernel (G-02-T18; SPEC-349 AC-21 to AC-23; DEC-625).

- `security_incident_timeline` (tenant, forced RLS, insert-only): an incident's attributed,
  append-only entries. A firm entry is the session's own person's (`author_user_id`, bound by the
  guard trigger); a system entry has no author and is the system's.
- `security_incident_decisions` (tenant, forced RLS, insert-only): the two-person decision, one
  row per decider: a partner and the QI, distinct (one row per seat and one per person), each a
  live person's own act, both of the same kind. The first names the second (`waiting_for`).
- `security_incidents` gains `closed_at` and `notification_started_at`; the app may now update
  `status`, `closed_at` and `notification_started_at` and nothing else, and only once both seats
  have decided the same kind (the guard trigger): `close_not_reportable` closes it,
  `start_notification` stamps the notification's start. The database stamps both times.
- `security_incident_reminders` (tenant, forced RLS, insert-only): one row per incident and day
  (20, 25 or 29) the FTC clock reminder went out, so a reminder is sent once.

Revision ID: 0240
Revises: 0220
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0240"
down_revision = "0220"
branch_labels = None
depends_on = None

_KINDS = "('close_not_reportable', 'start_notification')"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE security_incident_timeline (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            incident_id uuid NOT NULL,
            occurred_at timestamptz NOT NULL,
            code text NOT NULL CHECK (code ~ '^[a-z][a-z0-9_]{1,63}$'),
            facts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(facts) = 'object'),
            note text NULL CHECK (char_length(note) BETWEEN 1 AND 500),
            source text NOT NULL CHECK (source IN ('firm', 'system')),
            author_user_id uuid NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((source = 'firm') = (author_user_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, incident_id) REFERENCES security_incidents (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX security_incident_timeline_incident "
        "ON security_incident_timeline (tenant_id, incident_id, recorded_at)"
    )
    tenant_table(op, "security_incident_timeline")
    insert_only(op, "security_incident_timeline")
    op.execute("REVOKE TRUNCATE ON security_incident_timeline FROM abacus_app")
    insert_columns(
        op,
        "security_incident_timeline",
        (
            "tenant_id",
            "incident_id",
            "occurred_at",
            "code",
            "facts",
            "note",
            "source",
            "author_user_id",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION security_incident_timeline_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.source = 'firm' AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR NEW.author_user_id::text IS DISTINCT FROM current_setting('app.actor_id', true)
            ) THEN
                RAISE EXCEPTION 'a timeline entry is the session''s own person''s'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.source = 'system'
               AND current_setting('app.actor_kind', true) IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'a system timeline entry is the system''s'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.recorded_at := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_incident_timeline_guard BEFORE INSERT "
        "ON security_incident_timeline FOR EACH ROW "
        "EXECUTE FUNCTION security_incident_timeline_guard()"
    )

    op.execute(
        f"""
        CREATE TABLE security_incident_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            incident_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN {_KINDS}),
            seat text NOT NULL CHECK (seat IN ('partner', 'qualified_individual')),
            decided_by uuid NOT NULL,
            waiting_for uuid NULL,
            note text NULL CHECK (char_length(note) BETWEEN 1 AND 500),
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (waiting_for IS DISTINCT FROM decided_by),
            UNIQUE (tenant_id, incident_id, seat),
            UNIQUE (tenant_id, incident_id, decided_by),
            FOREIGN KEY (tenant_id, incident_id) REFERENCES security_incidents (tenant_id, id)
        )
        """
    )
    tenant_table(op, "security_incident_decisions")
    insert_only(op, "security_incident_decisions")
    op.execute("REVOKE TRUNCATE ON security_incident_decisions FROM abacus_app")
    insert_columns(
        op,
        "security_incident_decisions",
        ("tenant_id", "incident_id", "kind", "seat", "decided_by", "waiting_for", "note"),
    )
    # A live person's own decision; the second is the person the first named, of the same kind.
    op.execute(
        """
        CREATE FUNCTION security_incident_decisions_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_first record;
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.decided_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'an incident decision is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- Serialise the two decisions on the incident row (security review), so two first
            -- decisions can never both see none.
            PERFORM 1 FROM public.security_incidents
             WHERE tenant_id = NEW.tenant_id AND id = NEW.incident_id FOR UPDATE;
            SELECT kind, waiting_for INTO v_first FROM public.security_incident_decisions
             WHERE tenant_id = NEW.tenant_id AND incident_id = NEW.incident_id;
            IF FOUND THEN
                IF v_first.kind IS DISTINCT FROM NEW.kind
                   OR v_first.waiting_for IS DISTINCT FROM NEW.decided_by
                   OR NEW.waiting_for IS NOT NULL THEN
                    RAISE EXCEPTION 'the second decision is the named person''s, of the same kind'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF NEW.waiting_for IS NULL THEN
                RAISE EXCEPTION 'the first decision names the second decider'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.decided_at := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_incident_decisions_guard BEFORE INSERT "
        "ON security_incident_decisions FOR EACH ROW "
        "EXECUTE FUNCTION security_incident_decisions_guard()"
    )

    op.execute(
        """
        ALTER TABLE security_incidents
            ADD COLUMN closed_at timestamptz NULL,
            ADD COLUMN notification_started_at timestamptz NULL
        """
    )
    op.execute(
        "GRANT UPDATE (status, closed_at, notification_started_at) "
        "ON security_incidents TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION security_incidents_decided() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_kind text;
            v_count integer;
            v_kinds integer;
        BEGIN
            IF current_user <> 'abacus_app' THEN
                RETURN NEW;  -- the owner's maintenance; the app is held to the decisions
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human' THEN
                RAISE EXCEPTION 'an incident is decided by people'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT min(kind), count(*), count(DISTINCT kind) INTO v_kind, v_count, v_kinds
              FROM public.security_incident_decisions
             WHERE tenant_id = OLD.tenant_id AND incident_id = OLD.id;
            IF v_count IS DISTINCT FROM 2 OR v_kinds IS DISTINCT FROM 1 THEN
                RAISE EXCEPTION 'an incident needs both decisions first'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF v_kind = 'close_not_reportable' THEN
                IF OLD.status <> 'investigating' OR NEW.status <> 'closed'
                   OR NEW.notification_started_at IS DISTINCT FROM OLD.notification_started_at THEN
                    RAISE EXCEPTION 'a closing decision closes an open incident once'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                NEW.closed_at := clock_timestamp();
            ELSE
                IF OLD.notification_started_at IS NOT NULL OR NEW.status <> OLD.status
                   OR NEW.closed_at IS DISTINCT FROM OLD.closed_at THEN
                    RAISE EXCEPTION 'a notification decision starts the notification once'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                NEW.notification_started_at := clock_timestamp();
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_incidents_decided BEFORE UPDATE ON security_incidents "
        "FOR EACH ROW EXECUTE FUNCTION security_incidents_decided()"
    )

    op.execute(
        """
        CREATE TABLE security_incident_reminders (
            tenant_id uuid NOT NULL,
            incident_id uuid NOT NULL,
            day smallint NOT NULL CHECK (day IN (20, 25, 29)),
            sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, incident_id, day),
            FOREIGN KEY (tenant_id, incident_id) REFERENCES security_incidents (tenant_id, id)
        )
        """
    )
    tenant_table(op, "security_incident_reminders")
    insert_only(op, "security_incident_reminders")
    op.execute("REVOKE TRUNCATE ON security_incident_reminders FROM abacus_app")
    insert_columns(op, "security_incident_reminders", ("tenant_id", "incident_id", "day"))


def downgrade() -> None:
    op.execute("DROP TABLE security_incident_reminders")
    op.execute("DROP TRIGGER security_incidents_decided ON security_incidents")
    op.execute("DROP FUNCTION security_incidents_decided()")
    op.execute(
        "REVOKE UPDATE (status, closed_at, notification_started_at) "
        "ON security_incidents FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE security_incidents DROP COLUMN notification_started_at, DROP COLUMN closed_at"
    )
    op.execute("DROP TABLE security_incident_decisions")
    op.execute("DROP FUNCTION security_incident_decisions_guard()")
    op.execute("DROP TABLE security_incident_timeline")
    op.execute("DROP FUNCTION security_incident_timeline_guard()")
