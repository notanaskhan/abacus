"""Work slots: per-firm and per-engagement concurrency caps with fair hand-out (SPEC-003
AC-6 to AC-8, AC-13, AC-14; TASK-018 design §4 and §5, D3; ADR-071).

A workflow holds one slot of its work class for as long as it runs. A slot is granted only while
the class is under its capacity, the firm under its cap and the engagement under its cap, and
only to the first eligible waiter: round-robin across firms (the firm granted longest ago first),
then oldest first within a firm.

Fair hand-out has to see every firm's waiters, which row-level security forbids, so the ledger
(`work_slots`, `work_waiters`, `work_grants`) is platform-owned with no app privileges at all
(design D3). The app reaches it only through three SECURITY DEFINER functions, which take the
tenant from the session (`app.tenant_id`, set by `tenant_session`), never from an argument, and
return only the caller's own decision and estimate: no firm ever sees another's identity or load.
Rows hold identifiers and counts only. Leases use database time; an expired lease is reclaimed.

`sync_runs` and `agent_runs` gain `queued_reason` and `estimated_start_at`: a run waiting for a
slot stays `running` in the database and is reported as queued (design §5, revised).

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_CLASSES = "('interactive', 'time_sensitive', 'background', 'batch')"
_REASONS = "('firm_cap', 'engagement_cap', 'class_capacity', 'provider_capacity', 'deferred')"
_TABLES = ("work_slots", "work_waiters", "work_grants")
_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE work_slots (
            holder text PRIMARY KEY CHECK (length(holder) BETWEEN 1 AND 300),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_class text NOT NULL CHECK (work_class IN {_CLASSES}),
            acquired_at timestamptz NOT NULL,
            lease_until timestamptz NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX work_slots_class ON work_slots (work_class, tenant_id, engagement_id)"
    )
    op.execute(
        f"""
        CREATE TABLE work_waiters (
            holder text PRIMARY KEY CHECK (length(holder) BETWEEN 1 AND 300),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_class text NOT NULL CHECK (work_class IN {_CLASSES}),
            waiting_since timestamptz NOT NULL,
            last_seen timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX work_waiters_class ON work_waiters (work_class, waiting_since)")
    op.execute(
        f"""
        CREATE TABLE work_grants (
            tenant_id uuid NOT NULL,
            work_class text NOT NULL CHECK (work_class IN {_CLASSES}),
            granted_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX work_grants_class ON work_grants (work_class, granted_at)")
    for table in _TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")

    op.execute(
        """
        CREATE FUNCTION work_slot_acquire(
            p_holder text, p_engagement_id uuid, p_class text, p_firm_cap integer,
            p_engagement_cap integer, p_class_capacity integer, p_lease_seconds integer
        ) RETURNS TABLE (granted boolean, reason text, estimated_start_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_now timestamptz := clock_timestamp();
            v_first text;
            v_ahead integer;
            v_rate numeric;
            v_reason text;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'work slots need a tenant session'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_class NOT IN ('interactive', 'time_sensitive', 'background', 'batch')
               OR p_firm_cap < 0 OR p_engagement_cap < 0 OR p_class_capacity < 0
               OR p_lease_seconds < 1 THEN
                RAISE EXCEPTION 'invalid work slot request'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            PERFORM pg_advisory_xact_lock(hashtext('work_slots:' || p_class));

            -- Already holding: renew (idempotent per holder).
            UPDATE work_slots SET lease_until = v_now + make_interval(secs => p_lease_seconds)
             WHERE holder = p_holder AND tenant_id = v_tenant;
            IF FOUND THEN
                RETURN QUERY SELECT true, NULL::text, NULL::timestamptz;
                RETURN;
            END IF;

            DELETE FROM work_slots WHERE lease_until < v_now;
            DELETE FROM work_waiters WHERE last_seen < v_now - interval '5 minutes';
            DELETE FROM work_grants WHERE granted_at < v_now - interval '10 minutes';
            INSERT INTO work_waiters AS w
                (holder, tenant_id, engagement_id, work_class, waiting_since, last_seen)
            VALUES (p_holder, v_tenant, p_engagement_id, p_class, v_now, v_now)
            ON CONFLICT (holder) DO UPDATE SET last_seen = v_now
                WHERE w.tenant_id = v_tenant;

            -- The first eligible waiter of the class: under the firm and engagement caps;
            -- firms granted longest ago first, then oldest first.
            SELECT w.holder INTO v_first
              FROM work_waiters w
             WHERE w.work_class = p_class
               AND (SELECT count(*) FROM work_slots s
                     WHERE s.work_class = p_class AND s.tenant_id = w.tenant_id) < p_firm_cap
               AND (w.engagement_id IS NULL
                    OR (SELECT count(*) FROM work_slots s
                         WHERE s.work_class = p_class AND s.tenant_id = w.tenant_id
                           AND s.engagement_id = w.engagement_id) < p_engagement_cap)
             ORDER BY (SELECT max(g.granted_at) FROM work_grants g
                        WHERE g.work_class = p_class AND g.tenant_id = w.tenant_id)
                      ASC NULLS FIRST,
                      w.waiting_since, w.holder
             LIMIT 1;

            IF v_first = p_holder
               AND (SELECT count(*) FROM work_slots WHERE work_class = p_class) < p_class_capacity
            THEN
                INSERT INTO work_slots
                    (holder, tenant_id, engagement_id, work_class, acquired_at, lease_until)
                VALUES (p_holder, v_tenant, p_engagement_id, p_class, v_now,
                        v_now + make_interval(secs => p_lease_seconds));
                DELETE FROM work_waiters WHERE holder = p_holder;
                INSERT INTO work_grants (tenant_id, work_class, granted_at)
                VALUES (v_tenant, p_class, v_now);
                RETURN QUERY SELECT true, NULL::text, NULL::timestamptz;
                RETURN;
            END IF;

            -- Why the caller waits: only its own firm's and engagement's counts.
            IF (SELECT count(*) FROM work_slots
                 WHERE work_class = p_class AND tenant_id = v_tenant) >= p_firm_cap THEN
                v_reason := 'firm_cap';
            ELSIF p_engagement_id IS NOT NULL AND (SELECT count(*) FROM work_slots
                 WHERE work_class = p_class AND tenant_id = v_tenant
                   AND engagement_id = p_engagement_id) >= p_engagement_cap THEN
                v_reason := 'engagement_cap';
            ELSE
                v_reason := 'class_capacity';
            END IF;
            -- Estimate: waiters ahead in the class, at the class's grant rate over 10 minutes.
            SELECT count(*) INTO v_ahead FROM work_waiters w, work_waiters me
             WHERE me.holder = p_holder AND w.work_class = p_class
               AND (w.waiting_since, w.holder) < (me.waiting_since, me.holder);
            SELECT count(*) / 10.0 INTO v_rate FROM work_grants WHERE work_class = p_class;
            RETURN QUERY SELECT false, v_reason,
                CASE WHEN v_rate > 0
                     THEN v_now + make_interval(secs => ((v_ahead + 1) / v_rate) * 60)
                END;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION work_slot_release(p_holder text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'work slots need a tenant session'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            DELETE FROM work_slots WHERE holder = p_holder AND tenant_id = v_tenant;
            DELETE FROM work_waiters WHERE holder = p_holder AND tenant_id = v_tenant;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION work_slot_renew(p_holder text, p_lease_seconds integer)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'work slots need a tenant session'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            UPDATE work_slots
               SET lease_until = clock_timestamp() + make_interval(secs => p_lease_seconds)
             WHERE holder = p_holder AND tenant_id = v_tenant;
            RETURN FOUND;
        END
        $$
        """
    )
    for signature in (
        "work_slot_acquire(text, uuid, text, integer, integer, integer, integer)",
        "work_slot_release(text)",
        "work_slot_renew(text, integer)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")

    for table in ("sync_runs", "agent_runs"):
        op.execute(
            "ALTER TABLE " + table + " "
            "ADD COLUMN queued_reason text NULL CHECK (queued_reason IN " + _REASONS + "), "
            "ADD COLUMN estimated_start_at timestamptz NULL, "
            "ADD CONSTRAINT " + table + "_queued_running "
            "CHECK (status = 'running' OR (queued_reason IS NULL AND estimated_start_at IS NULL))"
        )
        op.execute(
            "GRANT UPDATE (queued_reason, estimated_start_at) ON " + table + " TO abacus_app"
        )


def downgrade() -> None:
    for table in ("sync_runs", "agent_runs"):
        op.execute(f"REVOKE UPDATE (queued_reason, estimated_start_at) ON {table} FROM abacus_app")
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {table}_queued_running, "
            "DROP COLUMN estimated_start_at, DROP COLUMN queued_reason"
        )
    op.execute("DROP FUNCTION work_slot_renew(text, integer)")
    op.execute("DROP FUNCTION work_slot_release(text)")
    op.execute(
        "DROP FUNCTION work_slot_acquire(text, uuid, text, integer, integer, integer, integer)"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
