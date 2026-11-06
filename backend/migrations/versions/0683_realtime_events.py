"""P-10 M4: the realtime invalidation log (P-10-T05; P-10 §3.8, §4.2; ADR-232; SPEC-647).

`realtime_events` is what `GET /v1/events` replays after a reconnect: identifiers and enums only,
kept 24 hours. A single subscriber writes it, so identity order is safe. No presence table.

- `realtime_channel(tenant)` names one of 16 NOTIFY channels, so a busy firm doesn't wake every
  listener.
- `prune_realtime_events(batch)` removes rows past 24 hours on `abacus_now()`, so the demo clock
  moves it. It is the only way a row goes.

Revision ID: 0683
Revises: 0682
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0683"
down_revision = "0682"
branch_labels = None
depends_on = None

INSERTS = ("tenant_id", "topic", "type", "ref_type", "ref_id", "version", "at")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE realtime_events (
            seq bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            topic text NOT NULL CHECK (length(topic) BETWEEN 1 AND 120),
            type text NOT NULL CHECK (type IN ('invalidate', 'notice', 'locked', 'resync')),
            ref_type text NULL CHECK (ref_type ~ '^[a-z][a-z_]{0,49}$'),
            ref_id uuid NULL,
            version bigint NULL CHECK (version >= 0),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, seq)
        )
        """
    )
    op.execute("CREATE INDEX realtime_events_at ON realtime_events USING brin (at)")
    op.execute("CREATE INDEX realtime_events_topic ON realtime_events (tenant_id, topic, seq)")
    tenant_table(op, "realtime_events")
    insert_columns(op, "realtime_events", INSERTS)
    insert_only(op, "realtime_events")
    op.execute(
        """
        CREATE FUNCTION realtime_channel(p_tenant uuid) RETURNS text
            LANGUAGE sql IMMUTABLE
        AS $$
            SELECT 'realtime_' || (abs(hashtext(p_tenant::text)) % 16)::text
        $$
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION realtime_channel(uuid) TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION prune_realtime_events(p_batch integer) RETURNS integer
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            gone integer;
        BEGIN
            IF v_tenant IS NULL
               OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'system'
               OR current_setting('app.actor_id', true)
                  IS DISTINCT FROM 'notifications.realtime_prune' THEN
                RAISE EXCEPTION 'only the realtime prune deletes realtime events'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            DELETE FROM public.realtime_events WHERE tenant_id = v_tenant AND seq IN (
                SELECT seq FROM public.realtime_events
                 WHERE tenant_id = v_tenant AND at < public.abacus_now() - interval '24 hours'
                 LIMIT p_batch
            );
            GET DIAGNOSTICS gone = ROW_COUNT;
            RETURN gone;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION prune_realtime_events(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION prune_realtime_events(integer) TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION prune_realtime_events(integer)")
    op.execute("DROP FUNCTION realtime_channel(uuid)")
    op.execute("DROP TABLE realtime_events")
