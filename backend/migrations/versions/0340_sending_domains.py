"""Sender domains, the client-mail gate and the From on a message (R-01-T27; R-01 §4.2, story
8.3 and 9.2; C16 v1.1 §sending domains; DEC-59, DEC-950 to DEC-955).

- `sending_domains` (new, communications, forced RLS): a firm's own domain for client mail, an
  SES identity with Easy DKIM and a custom MAIL FROM (`bounce.<domain>`). `status` moves
  `pending_dns` -> `verified` | `failed` -> `revoked` (a guard trigger refuses any other move;
  `revoked` is final). At most one live domain (`pending_dns` or `verified`) per firm, and a live
  domain belongs to one firm only: the second index is global, so another firm can't claim a
  domain that is pending or verified for this one (SES identities are per account, not per
  firm; DEC-951). The DNS records are public values; nothing Restricted is stored.
- `firm_mail_policies` (new, communications, forced RLS): whether a firm's client mail is open
  (the M10 flip; story 9.2). The app can't read or write the table: it reads through the definer
  `client_mail_enabled()` (the row, else the firm's `synthetic`: a synthetic firm's mail goes to
  the sink, so it is open), and only `abacus_ops` writes, through `set_client_mail(...)`, which
  names two different people to open it and audits the change in the firm's trail.
- `messages` gains `from_domain`: the domain the message was sent From (the firm's verified one,
  or the neutral sender's), set on insert.

`email_suppressions` and `message_deliveries` already exist (Q-01-T46, 0104); a message's delivery
status is read from its latest delivery event (DEC-952), so `messages` stays insert-only.

Revision ID: 0340
Revises: 0320
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0340"
down_revision = "0320"
branch_labels = None
depends_on = None

_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_STATE = "client_mail_enabled()"
_SET = "set_client_mail(uuid, boolean, text, text, text)"
_GUARD = "sending_domains_transition()"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sending_domains (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            domain text NOT NULL
                CHECK (domain ~ '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$'
                       AND length(domain) <= 253),
            from_local_part text NOT NULL DEFAULT 'clients'
                CHECK (from_local_part ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
            mail_from_domain text NOT NULL,
            status text NOT NULL DEFAULT 'pending_dns'
                CHECK (status IN ('pending_dns', 'verified', 'failed', 'revoked')),
            dkim_records jsonb NOT NULL CHECK (jsonb_typeof(dkim_records) = 'array'),
            dkim_status text NOT NULL DEFAULT 'pending'
                CHECK (dkim_status IN ('pending', 'verified', 'failed')),
            mail_from_status text NOT NULL DEFAULT 'pending'
                CHECK (mail_from_status IN ('pending', 'verified', 'failed')),
            ses_identity_ref text NOT NULL,
            requested_by uuid NOT NULL,
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            verified_at timestamptz NULL,
            last_checked_at timestamptz NULL,
            failure_reason text NULL
                CHECK (failure_reason IN ('dkim_not_verified', 'mail_from_not_verified',
                                          'identity_missing')),
            revoked_at timestamptz NULL,
            revoked_by uuid NULL,
            CHECK ((status = 'verified') = (verified_at IS NOT NULL)
                   OR status IN ('failed', 'revoked')),
            CHECK ((status = 'failed') = (failure_reason IS NOT NULL) OR status = 'revoked'),
            CHECK ((status = 'revoked') = (revoked_at IS NOT NULL AND revoked_by IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX sending_domains_live_per_firm ON sending_domains (tenant_id) "
        "WHERE status IN ('pending_dns', 'verified')"
    )
    op.execute(
        "CREATE UNIQUE INDEX sending_domains_live_domain ON sending_domains (domain) "
        "WHERE status IN ('pending_dns', 'verified')"
    )
    tenant_table(op, "sending_domains")
    op.execute("REVOKE UPDATE, DELETE ON sending_domains FROM abacus_app")
    insert_columns(
        op,
        "sending_domains",
        (
            "tenant_id",
            "domain",
            "from_local_part",
            "mail_from_domain",
            "dkim_records",
            "ses_identity_ref",
            "requested_by",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, dkim_records, dkim_status, mail_from_status, verified_at, "
        "last_checked_at, failure_reason, revoked_at, revoked_by) ON sending_domains "
        "TO abacus_app"
    )
    op.execute(
        f"""
        CREATE FUNCTION {_GUARD} RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status = NEW.status THEN
                IF OLD.status = 'revoked' THEN
                    RAISE EXCEPTION 'a revoked sending domain is final'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF (OLD.status, NEW.status) IN (('pending_dns', 'verified'), ('pending_dns', 'failed'),
                                            ('pending_dns', 'revoked'), ('verified', 'failed'),
                                            ('verified', 'revoked'), ('failed', 'revoked')) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'sending domain % -> % is not a transition', OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER sending_domains_transition BEFORE UPDATE ON sending_domains "
        f"FOR EACH ROW EXECUTE FUNCTION {_GUARD}"
    )

    op.execute(
        """
        CREATE TABLE firm_mail_policies (
            tenant_id uuid PRIMARY KEY,
            client_mail_enabled boolean NOT NULL DEFAULT false,
            enabled_by text NULL,
            second_by text NULL,
            request_ref text NULL,
            changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (NOT client_mail_enabled
                   OR (enabled_by IS NOT NULL AND second_by IS NOT NULL
                       AND enabled_by <> second_by))
        )
        """
    )
    tenant_table(op, "firm_mail_policies")
    op.execute("REVOKE ALL ON firm_mail_policies FROM abacus_app")
    op.execute(
        f"""
        CREATE FUNCTION {_STATE} RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
            SELECT coalesce(
                (SELECT p.client_mail_enabled FROM public.firm_mail_policies p
                  WHERE p.tenant_id = {_TENANT}),
                (SELECT f.synthetic FROM public.firms f WHERE f.tenant_id = {_TENANT}),
                false)
        $$
        """  # noqa: S608 -- fixed SQL
    )
    op.execute(
        """
        CREATE FUNCTION set_client_mail(
            p_tenant uuid, p_enabled boolean, p_first text, p_second text, p_request_ref text
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE
            v_tenant text := current_setting('app.tenant_id', true);
            v_kind text := current_setting('app.actor_kind', true);
            v_actor text := current_setting('app.actor_id', true);
        BEGIN
            IF p_first IS NULL OR (p_enabled AND (p_second IS NULL OR p_first = p_second)) THEN
                RAISE EXCEPTION 'opening client mail names two different people'
                    USING ERRCODE = 'check_violation';
            END IF;
            -- The firm's own row-level security, as the operator (as `set_platform_control`).
            PERFORM set_config('app.tenant_id', p_tenant::text, true);
            PERFORM set_config('app.actor_kind', 'system', true);
            PERFORM set_config('app.actor_id', 'operator:' || p_first, true);
            IF NOT EXISTS (SELECT 1 FROM public.firms f WHERE f.tenant_id = p_tenant) THEN
                RAISE EXCEPTION 'no such firm' USING ERRCODE = 'no_data_found';
            END IF;
            INSERT INTO public.firm_mail_policies AS p
                   (tenant_id, client_mail_enabled, enabled_by, second_by, request_ref)
            VALUES (p_tenant, p_enabled, p_first, p_second, p_request_ref)
            ON CONFLICT (tenant_id) DO UPDATE
               SET client_mail_enabled = EXCLUDED.client_mail_enabled,
                   enabled_by = EXCLUDED.enabled_by, second_by = EXCLUDED.second_by,
                   request_ref = EXCLUDED.request_ref, changed_at = clock_timestamp();
            INSERT INTO public.audit_events
                   (tenant_id, actor_kind, actor_id, action, target_type, target_id)
            VALUES (p_tenant, 'system', 'operator:' || p_first,
                    CASE WHEN p_enabled THEN 'firm_mail_policy.client_mail_enabled'
                         ELSE 'firm_mail_policy.client_mail_disabled' END,
                    'firm', p_tenant::text);
            PERFORM set_config('app.tenant_id', coalesce(v_tenant, ''), true);
            PERFORM set_config('app.actor_kind', coalesce(v_kind, ''), true);
            PERFORM set_config('app.actor_id', coalesce(v_actor, ''), true);
            RETURN p_enabled;
        END $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_STATE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_STATE} TO abacus_app")
    op.execute(f"REVOKE ALL ON FUNCTION {_SET} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SET} TO abacus_ops")

    op.execute("ALTER TABLE messages ADD COLUMN from_domain text NULL")
    op.execute("GRANT INSERT (from_domain) ON messages TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (from_domain) ON messages FROM abacus_app")
    op.execute("ALTER TABLE messages DROP COLUMN from_domain")
    op.execute(f"DROP FUNCTION {_SET}")
    op.execute(f"DROP FUNCTION {_STATE}")
    op.execute("DROP TABLE firm_mail_policies")
    op.execute("DROP TABLE sending_domains")
    op.execute(f"DROP FUNCTION {_GUARD}")
