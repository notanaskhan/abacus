"""Platform tenancy: region and tenant keys on firms, kill-switch controls, operator provisioning
(Q-01-T19; ADR-157 proposed, P-66; ADR-156, P-65; R-35).

- `firms.region` (`'us'` only; changing region needs a new tenant), `kms_key_arn`,
  `kms_key_status`, `kms_replica_verified_at`. The app may read all four and update only the key
  columns (the key workflow runs in the tenant's context); `region` and `synthetic` stay the
  owner's.
- `platform_controls` (global): one row per control, scope and route; the `control` CHECK is the
  kill-switch registry (ADR-157). `platform_control_changes` (global, insert-only, a trigger
  refuses UPDATE and DELETE) records every change. `firm_provisioning_requests` (global) makes
  provisioning idempotent. No app privileges on any of the three.
- Definers: `platform_control_state()` (the app's only read of controls), and, for the
  `abacus_ops` role only (bootstrap.sql), `set_platform_control(...)` (a firm-scoped change is
  audited in that firm as `platform_control.changed` by `operator:<handle>`) and
  `provision_firm(...)` (refuses any region but `us`; the only way besides `firm_signup` to
  create a firm). The `platform_control.changed` outbox event follows with its consumer.

Revision ID: 0086
Revises: 0085
"""

from __future__ import annotations

from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None

_STATE = "platform_control_state()"
_SET = "set_platform_control(text, text, uuid, text, boolean, text, text, text)"
_PROVISION = "provision_firm(text, boolean, text, text, text, text)"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE firms
            ADD COLUMN region text NOT NULL DEFAULT 'us' CHECK (region = 'us'),
            ADD COLUMN kms_key_arn text NULL CHECK (length(kms_key_arn) BETWEEN 1 AND 300),
            ADD COLUMN kms_key_status text NOT NULL DEFAULT 'none'
                CHECK (kms_key_status IN ('none', 'pending', 'active', 'replica_verified',
                                          'pending_deletion')),
            ADD COLUMN kms_replica_verified_at timestamptz NULL
        """
    )
    op.execute(
        "GRANT UPDATE (kms_key_arn, kms_key_status, kms_replica_verified_at) ON firms "
        "TO abacus_app"
    )

    columns = """
            control text NOT NULL
                CHECK (control IN ('ai_pause', 'model_route_block', 'email_pause', 'read_only',
                                   'portal_sign_in_disabled')),
            scope text NOT NULL CHECK (scope IN ('platform', 'firm')),
            tenant_id uuid NULL,
            route text NULL,
            active boolean NOT NULL,
            reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 200),
            set_by text NOT NULL CHECK (length(set_by) BETWEEN 1 AND 100),
            request_ref text NULL CHECK (length(request_ref) BETWEEN 1 AND 200),
            version integer NOT NULL CHECK (version >= 1),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((scope = 'firm') = (tenant_id IS NOT NULL)),
            CHECK ((control = 'model_route_block') = (route IS NOT NULL))
    """
    op.execute(f"CREATE TABLE platform_controls ({columns})")
    op.execute(
        "CREATE UNIQUE INDEX platform_controls_one ON platform_controls (control, scope, "
        "coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), coalesce(route, ''))"
    )
    op.execute(
        "CREATE TABLE platform_control_changes (id bigserial PRIMARY KEY, "
        f"changed_at timestamptz NOT NULL DEFAULT clock_timestamp(), {columns})"
    )
    op.execute(
        """
        CREATE FUNCTION platform_control_changes_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'platform_control_changes is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER platform_control_changes_immutable BEFORE UPDATE OR DELETE "
        "ON platform_control_changes FOR EACH ROW "
        "EXECUTE FUNCTION platform_control_changes_immutable()"
    )
    op.execute(
        """
        CREATE TABLE firm_provisioning_requests (
            idempotency_key text PRIMARY KEY CHECK (length(idempotency_key) BETWEEN 8 AND 200),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            operator text NOT NULL CHECK (length(operator) BETWEEN 1 AND 100)
        )
        """
    )
    for table in ("platform_controls", "platform_control_changes", "firm_provisioning_requests"):
        op.execute(f"REVOKE ALL ON {table} FROM abacus_app")
    op.execute("REVOKE ALL ON SEQUENCE platform_control_changes_id_seq FROM abacus_app")

    op.execute(
        """
        CREATE FUNCTION platform_control_state()
        RETURNS TABLE (control text, scope text, tenant_id uuid, route text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            SELECT c.control, c.scope, c.tenant_id, c.route
              FROM public.platform_controls c WHERE c.active
             ORDER BY c.control, c.scope, c.tenant_id, c.route
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION set_platform_control(
            p_control text, p_scope text, p_tenant uuid, p_route text, p_active boolean,
            p_reason text, p_set_by text, p_request_ref text
        ) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_version integer;
            v_tenant text := current_setting('app.tenant_id', true);
            v_kind text := current_setting('app.actor_kind', true);
            v_actor text := current_setting('app.actor_id', true);
        BEGIN
            INSERT INTO public.platform_controls AS c
                   (control, scope, tenant_id, route, active, reason, set_by, request_ref,
                    version)
            VALUES (p_control, p_scope, p_tenant, p_route, p_active, p_reason, p_set_by,
                    p_request_ref, 1)
            ON CONFLICT (control, scope,
                         coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid),
                         coalesce(route, ''))
            DO UPDATE SET active = EXCLUDED.active, reason = EXCLUDED.reason,
                          set_by = EXCLUDED.set_by, request_ref = EXCLUDED.request_ref,
                          version = c.version + 1, updated_at = clock_timestamp()
            RETURNING c.version INTO v_version;
            INSERT INTO public.platform_control_changes
                   (control, scope, tenant_id, route, active, reason, set_by, request_ref,
                    version)
            VALUES (p_control, p_scope, p_tenant, p_route, p_active, p_reason, p_set_by,
                    p_request_ref, v_version);
            IF p_scope = 'firm' THEN
                -- The firm's own audit trail, as the operator (the row passes the firm's
                -- row-level security and the actor check); the caller's settings return.
                PERFORM set_config('app.tenant_id', p_tenant::text, true);
                PERFORM set_config('app.actor_kind', 'system', true);
                PERFORM set_config('app.actor_id', 'operator:' || p_set_by, true);
                INSERT INTO public.audit_events
                       (tenant_id, actor_kind, actor_id, action, target_type, target_id)
                VALUES (p_tenant, 'system', 'operator:' || p_set_by, 'platform_control.changed',
                        'firm', p_tenant::text);
                PERFORM set_config('app.tenant_id', coalesce(v_tenant, ''), true);
                PERFORM set_config('app.actor_kind', coalesce(v_kind, ''), true);
                PERFORM set_config('app.actor_id', coalesce(v_actor, ''), true);
            END IF;
            RETURN v_version;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION provision_firm(
            p_name text, p_synthetic boolean, p_region text, p_time_zone text,
            p_idempotency_key text, p_operator text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_tenant uuid;
            v_previous text := current_setting('app.tenant_id', true);
        BEGIN
            IF p_region IS DISTINCT FROM 'us' THEN
                RAISE EXCEPTION 'region % is not offered', p_region
                    USING ERRCODE = 'check_violation';
            END IF;
            SELECT r.tenant_id INTO v_tenant FROM public.firm_provisioning_requests r
             WHERE r.idempotency_key = p_idempotency_key;
            IF v_tenant IS NOT NULL THEN
                RETURN v_tenant;
            END IF;
            v_tenant := gen_random_uuid();
            PERFORM set_config('app.tenant_id', v_tenant::text, true);
            INSERT INTO public.firms (tenant_id, name, synthetic, region, time_zone)
            VALUES (v_tenant, p_name, p_synthetic, p_region, p_time_zone);
            PERFORM set_config('app.tenant_id', coalesce(v_previous, ''), true);
            INSERT INTO public.firm_provisioning_requests (idempotency_key, tenant_id, operator)
            VALUES (p_idempotency_key, v_tenant, p_operator);
            RETURN v_tenant;
        END $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_STATE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_STATE} TO abacus_app")
    for signature in (_SET, _PROVISION):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_ops")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_PROVISION}")
    op.execute(f"DROP FUNCTION {_SET}")
    op.execute(f"DROP FUNCTION {_STATE}")
    op.execute("DROP TABLE firm_provisioning_requests")
    op.execute("DROP TABLE platform_control_changes")
    op.execute("DROP FUNCTION platform_control_changes_immutable()")
    op.execute("DROP TABLE platform_controls")
    op.execute(
        "REVOKE UPDATE (kms_key_arn, kms_key_status, kms_replica_verified_at) ON firms "
        "FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE firms DROP COLUMN kms_replica_verified_at, DROP COLUMN kms_key_status, "
        "DROP COLUMN kms_key_arn, DROP COLUMN region"
    )
