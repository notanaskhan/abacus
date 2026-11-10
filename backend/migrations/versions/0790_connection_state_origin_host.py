"""A started connection remembers the host it began on; the connect host can hand the provider's
answer back to it (A-02-T33; TASK-6902; DEC-3902; ADR-152, ADR-163 §5).

Intuit registers exact redirect URIs, so every firm's flow returns to one fixed host,
`connect.<domain>` (DEC-3901). A portal session is pinned to the firm's own host (ADR-163 §5,
ADR-168), so the connect host can't complete the flow itself: it sends the browser on to the host
the flow began on, with the provider's query unchanged, and completion runs there as before.

- `connection_states.origin_host`: the request's `Host` at start (after `TrustedHosts`, without its
  port, lower case), never anything the query says. Insert-only for the app, like the rest of the
  state. Null for a state started before this migration or on a host that is not a host name; such
  a state is never handed on.
- `connection_state_firms`: a global note of each state's hash and firm (no app privilege at all,
  like `portal_domains`), written by the `connection_state_firm_note` trigger as a state is
  inserted. Row-level security is forced on `connection_states`, so a lookup before any tenant is
  known needs the firm first; this is where it comes from. The hash alone names nothing.
- `connection_state_origin(state_hash, app_host)`: a pre-session definer. It finds the hash's firm,
  reads the state in that firm's tenant scope only (`app.tenant_id` set for the call and restored,
  as 0156's link definers do), and answers the stored origin host only for a state that is unused
  and unexpired, and only when that host is the firm app's host (`app_host`, from configuration)
  or an active portal host of the state's own firm. Anything else, unknown hashes included, is
  null: one answer, no tenant, no firm, no reason. It reads; it never spends the state, which
  stays for `complete` alone (single use, the person's own, with its sealed PKCE verifier;
  DEC-515 L6).

Expand-only; the downgrade drops the function, the trigger, the note table and the column.

Revision ID: 0790
Revises: 0763
"""

from __future__ import annotations

from alembic import op

revision = "0790"
down_revision = "0763"
branch_labels = None
depends_on = None

# A host name, one label or more (a local stack's `localhost` is one label); no port, no dot at
# the end. The portal hosts' own CHECK (0111) needs two labels; this column needs only the shape.
_HOST = "~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$'"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE connection_states
            ADD COLUMN origin_host text NULL
                CONSTRAINT connection_states_origin_host_check
                CHECK (origin_host = lower(origin_host) AND char_length(origin_host) <= 253
                       AND origin_host {_HOST})
        """
    )
    op.execute("GRANT INSERT (origin_host) ON connection_states TO abacus_app")
    op.execute(
        """
        CREATE TABLE connection_state_firms (
            state_hash text PRIMARY KEY CHECK (state_hash ~ '^[0-9a-f]{64}$'),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute("REVOKE ALL ON connection_state_firms FROM PUBLIC, abacus_app")
    op.execute(
        """
        CREATE FUNCTION connection_state_firm_note() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        BEGIN
            INSERT INTO public.connection_state_firms (state_hash, tenant_id)
            VALUES (NEW.state_hash, NEW.tenant_id);
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION connection_state_firm_note() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER connection_state_firm_note AFTER INSERT ON connection_states "
        "FOR EACH ROW EXECUTE FUNCTION connection_state_firm_note()"
    )
    op.execute(
        """
        CREATE FUNCTION connection_state_origin(p_state_hash text, p_app_host text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_previous text := current_setting('app.tenant_id', true);
            v_firm uuid;
            v_host text;
        BEGIN
            SELECT f.tenant_id INTO v_firm FROM public.connection_state_firms f
             WHERE f.state_hash = p_state_hash;
            IF v_firm IS NULL THEN
                RETURN NULL;
            END IF;
            PERFORM set_config('app.tenant_id', v_firm::text, true);
            SELECT s.origin_host INTO v_host FROM public.connection_states s
             WHERE s.state_hash = p_state_hash
               AND s.tenant_id = v_firm
               AND s.used_at IS NULL
               AND s.expires_at > clock_timestamp()
               AND s.origin_host IS NOT NULL
               AND (s.origin_host = lower(p_app_host)
                    OR EXISTS (SELECT 1 FROM public.portal_domains d
                                WHERE d.hostname = s.origin_host
                                  AND d.tenant_id = v_firm
                                  AND d.status = 'active'));
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            RETURN v_host;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION connection_state_origin(text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION connection_state_origin(text, text) TO abacus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION connection_state_origin(text, text)")
    op.execute("DROP TRIGGER connection_state_firm_note ON connection_states")
    op.execute("DROP FUNCTION connection_state_firm_note()")
    op.execute("DROP TABLE connection_state_firms")
    op.execute("REVOKE INSERT (origin_host) ON connection_states FROM abacus_app")
    op.execute("ALTER TABLE connection_states DROP COLUMN origin_host")
