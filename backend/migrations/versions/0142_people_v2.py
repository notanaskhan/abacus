"""People v2 (G-01-T05; G-01 sections 3.3 to 3.5, 4.2; ADR P-10, DEC-21, DEC-35; DEC-285).

- `memberships` gains `role_template` (the eight ADM-02 templates; back-filled for staff from the
  firm role and level, NULL for client memberships), `access_ends_on`, `revoked_reason`,
  `revoked_on_behalf_of` and `version`. The app may update the person's attributes and template
  (column grants, its own firm through RLS); firm roles and revocation stay behind the definers,
  which keep the firm's last firm administrator and last security administrator.
- `staff_invitations` gains what the membership takes on acceptance: template, level, office,
  teams, service lines, access end, offshore, the invited person's name and title.
- `add_staff_membership` (same signature) gives a new membership its template from the firm role
  and clears a deactivation when it reactivates one; `membership_set_firm_role` (same signature)
  also keeps the last `security_admin` (AC4.3).
- `membership_deactivate(user, reason, on_behalf_of, end_sessions)`: AC4.4. The membership is
  revoked with its reason; the person's live staff sessions end (`membership_removed`) when the
  caller says no other firm holds them (a session spans memberships, and this definer sees only
  this firm's under row-level security).
- `staff_last_sign_ins()`, `staff_sign_in_history(user, limit)`: the session firm's staff only,
  and only sessions that began while the membership here was active and no other firm held them
  (staff sessions carry no firm, 0116; DEC-286). `last_sign_ins` is for active members only.

Revision ID: 0142
Revises: 0133
"""

from __future__ import annotations

from alembic import op

revision = "0142"
down_revision = "0133"
branch_labels = None
depends_on = None

_TEMPLATES = (
    "('partner', 'manager', 'tax_reviewer', 'senior', 'staff', 'tax_preparer', "
    "'firm_admin', 'it_security')"
)
_LEVELS = "('partner', 'manager', 'senior', 'staff', 'seasonal', 'admin')"
_FIRM_ROLES = "('firm_admin', 'practice_leader', 'quality_partner', 'security_admin')"
_NEW_FUNCTIONS = (
    "membership_deactivate(uuid, text, uuid, boolean)",
    "staff_last_sign_ins()",
    "staff_sign_in_history(uuid, integer)",
)
_MEMBER_UPDATES = (
    "role_template, level, job_title, office_id, service_lines, access_ends_on, offshore, version"
)
_INVITATION_COLUMNS = (
    "role_template, level, office_id, team_ids, service_lines, access_ends_on, offshore, "
    "display_name, job_title"
)

# The template a staff membership takes from its firm role and level (back-fill and insert).
_DERIVED = """CASE
            WHEN {role} = 'firm_admin' THEN 'firm_admin'
            WHEN {role} = 'security_admin' THEN 'it_security'
            WHEN {level} = 'partner' THEN 'partner'
            WHEN {level} = 'manager' THEN 'manager'
            WHEN {level} = 'senior' THEN 'senior'
            WHEN {level} = 'seasonal' THEN 'tax_preparer'
            ELSE 'staff' END"""

_BACKFILL = """
        UPDATE memberships SET role_template = CASE
            WHEN firm_role = 'firm_admin' THEN 'firm_admin'
            WHEN firm_role = 'security_admin' THEN 'it_security'
            WHEN level = 'partner' THEN 'partner'
            WHEN level = 'manager' THEN 'manager'
            WHEN level = 'senior' THEN 'senior'
            WHEN level = 'seasonal' THEN 'tax_preparer'
            ELSE 'staff' END
         WHERE kind = 'staff'
"""

_ADD_STAFF_MEMBERSHIP = """
        CREATE OR REPLACE FUNCTION add_staff_membership(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_kind text;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            IF p_role IS NOT NULL
               AND p_role NOT IN {roles} THEN
                RAISE EXCEPTION 'not a firm role' USING ERRCODE = 'check_violation';
            END IF;
            SELECT kind INTO v_kind FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user FOR UPDATE;
            IF v_kind = 'client' THEN
                RETURN 'client_contact';
            ELSIF v_kind IS NULL THEN
                INSERT INTO public.memberships (tenant_id, user_id, firm_role, kind{template_col})
                VALUES (v_tenant, p_user, p_role, 'staff'{template_val});
            ELSE
                UPDATE public.memberships
                   SET status = 'active', revoked_at = NULL, firm_role = p_role{reactivate}
                 WHERE tenant_id = v_tenant AND user_id = p_user;
            END IF;
            RETURN 'ok';
        END $$
"""

_SET_FIRM_ROLE = """
        CREATE OR REPLACE FUNCTION membership_set_firm_role(p_user uuid, p_role text) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
                v_found boolean;
        BEGIN
            IF p_role IS NOT NULL
               AND p_role NOT IN {roles} THEN
                RAISE EXCEPTION 'not a firm role' USING ERRCODE = 'check_violation';
            END IF;
            SELECT true, firm_role INTO v_found, v_current FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user
               AND kind = 'staff' AND status = 'active'
             FOR UPDATE;
            IF v_found IS NULL THEN RETURN 'not_found'; END IF;
            IF v_current IN ({guarded}) AND p_role IS DISTINCT FROM v_current AND NOT EXISTS (
                SELECT 1 FROM public.memberships
                 WHERE tenant_id = v_tenant AND firm_role = v_current
                   AND status = 'active' AND kind = 'staff' AND user_id <> p_user
            ) THEN
                RETURN 'last_admin';
            END IF;
            UPDATE public.memberships SET firm_role = p_role
             WHERE tenant_id = v_tenant AND user_id = p_user;
            RETURN 'ok';
        END $$
"""

_DEACTIVATE = """
        CREATE FUNCTION membership_deactivate(
            p_user uuid, p_reason text, p_on_behalf_of uuid, p_end_sessions boolean
        ) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                v_current text;
                v_found boolean;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            IF p_reason NOT IN ('manual', 'access_ended', 'scim_deprovisioned') THEN
                RAISE EXCEPTION 'not a deactivation reason' USING ERRCODE = 'check_violation';
            END IF;
            SELECT true, firm_role INTO v_found, v_current FROM public.memberships
             WHERE tenant_id = v_tenant AND user_id = p_user
               AND kind = 'staff' AND status = 'active'
             FOR UPDATE;
            IF v_found IS NULL THEN RETURN 'not_found'; END IF;
            IF v_current IN ('firm_admin', 'security_admin') AND NOT EXISTS (
                SELECT 1 FROM public.memberships
                 WHERE tenant_id = v_tenant AND firm_role = v_current
                   AND status = 'active' AND kind = 'staff' AND user_id <> p_user
            ) THEN
                RETURN 'last_admin';
            END IF;
            UPDATE public.memberships
               SET status = 'revoked', revoked_at = clock_timestamp(),
                   revoked_reason = p_reason, revoked_on_behalf_of = p_on_behalf_of,
                   version = version + 1
             WHERE tenant_id = v_tenant AND user_id = p_user;
            -- The caller says whether another firm still holds the person (this definer sees only
            -- this firm's memberships under row-level security); a session spans firms.
            IF p_end_sessions THEN
                UPDATE public.auth_sessions
                   SET ended_at = clock_timestamp(), end_reason = 'membership_removed'
                 WHERE user_id = p_user AND surface = 'staff' AND ended_at IS NULL;
            END IF;
            RETURN 'ok';
        END $$
"""

# A staff session (0116: `tenant_id` NULL) spans firms, so a sign-in counts for this firm only
# when it began while the person's membership here was active (DEC-286): nothing before they
# joined or after they left. Memberships are under forced row-level security even here, so the
# definer can't see the person's other firms; the service drops the history of anyone who belongs
# or belonged to another firm (identity's sign-in role can see that), so a consultant's sign-ins
# elsewhere never show.
_LAST_SIGN_INS = """
        CREATE FUNCTION staff_last_sign_ins()
        RETURNS TABLE (user_id uuid, signed_in_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            RETURN QUERY
            SELECT s.user_id, max(s.created_at)
              FROM public.auth_sessions s
              JOIN public.memberships m ON m.user_id = s.user_id
             WHERE m.tenant_id = v_tenant AND m.kind = 'staff' AND m.status = 'active'
               AND s.surface = 'staff' AND
                   m.created_at <= s.created_at
               AND (m.revoked_at IS NULL OR s.created_at < m.revoked_at)
             GROUP BY s.user_id;
        END $$
"""

_SIGN_IN_HISTORY = """
        CREATE FUNCTION staff_sign_in_history(p_user uuid, p_limit integer)
        RETURNS TABLE (signed_in_at timestamptz, provider text, mfa boolean)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s'
        AS $$
        DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN RAISE EXCEPTION 'no tenant'; END IF;
            RETURN QUERY
            SELECT s.created_at, s.provider, s.mfa_at IS NOT NULL
              FROM public.auth_sessions s
              JOIN public.memberships m ON m.user_id = s.user_id
             WHERE m.tenant_id = v_tenant AND m.kind = 'staff' AND s.user_id = p_user
               AND s.surface = 'staff' AND
                   m.created_at <= s.created_at
               AND (m.revoked_at IS NULL OR s.created_at < m.revoked_at)
             ORDER BY s.created_at DESC
             LIMIT least(greatest(p_limit, 1), 20);
        END $$
"""


def _staff_functions(*, v2: bool) -> None:
    if v2:
        template = _DERIVED.format(role="p_role", level="NULL::text")
        op.execute(
            _ADD_STAFF_MEMBERSHIP.format(
                roles=_FIRM_ROLES,
                template_col=", role_template",
                template_val=f", {template}",
                # A reactivated member's template follows the firm role it gets back (the
                # invitation's terms, if any, are applied after).
                reactivate=", revoked_reason = NULL, revoked_on_behalf_of = NULL, "
                "version = version + 1, role_template = "
                + _DERIVED.format(role="p_role", level="level"),
            )
        )
        op.execute(
            _SET_FIRM_ROLE.format(roles=_FIRM_ROLES, guarded="'firm_admin', 'security_admin'")
        )
    else:  # 0127's bodies
        op.execute(
            _ADD_STAFF_MEMBERSHIP.format(
                roles=_FIRM_ROLES, template_col="", template_val="", reactivate=""
            )
        )
        op.execute(_SET_FIRM_ROLE.format(roles=_FIRM_ROLES, guarded="'firm_admin'"))


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE memberships
            ADD COLUMN role_template text NULL CHECK (role_template IN {_TEMPLATES}),
            ADD COLUMN access_ends_on date NULL,
            ADD COLUMN revoked_reason text NULL
                CHECK (revoked_reason IN ('manual', 'access_ended', 'scim_deprovisioned')),
            ADD COLUMN revoked_on_behalf_of uuid NULL,
            ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            ADD CONSTRAINT memberships_client_has_no_template
                CHECK (kind = 'staff' OR role_template IS NULL)
        """
    )
    op.execute(_BACKFILL)
    op.execute(f"GRANT UPDATE ({_MEMBER_UPDATES}) ON memberships TO abacus_app")
    op.execute(
        f"""
        ALTER TABLE staff_invitations
            ADD COLUMN role_template text NULL CHECK (role_template IN {_TEMPLATES}),
            ADD COLUMN level text NULL CHECK (level IN {_LEVELS}),
            ADD COLUMN office_id uuid NULL,
            ADD COLUMN team_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(team_ids) <= 20),
            ADD COLUMN service_lines text[] NOT NULL DEFAULT '{{}}'
                CHECK (service_lines <@ ARRAY['audit', 'tax', 'cas', 'advisory']::text[]),
            ADD COLUMN access_ends_on date NULL,
            ADD COLUMN offshore boolean NOT NULL DEFAULT false,
            ADD COLUMN display_name text NULL CHECK (length(display_name) BETWEEN 1 AND 200),
            ADD COLUMN job_title text NULL CHECK (length(job_title) BETWEEN 1 AND 120),
            ADD CONSTRAINT staff_invitations_office_fkey
                FOREIGN KEY (tenant_id, office_id) REFERENCES offices (tenant_id, id),
            ADD CONSTRAINT staff_invitations_seasonal_ends
                CHECK (level IS DISTINCT FROM 'seasonal' OR access_ends_on IS NOT NULL)
        """
    )
    op.execute(f"GRANT INSERT ({_INVITATION_COLUMNS}) ON staff_invitations TO abacus_app")
    _staff_functions(v2=True)
    for body in (_DEACTIVATE, _LAST_SIGN_INS, _SIGN_IN_HISTORY):
        op.execute(body)
    for function in _NEW_FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_NEW_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    _staff_functions(v2=False)
    op.execute(f"REVOKE INSERT ({_INVITATION_COLUMNS}) ON staff_invitations FROM abacus_app")
    op.execute(
        "ALTER TABLE staff_invitations DROP CONSTRAINT staff_invitations_seasonal_ends, "
        "DROP CONSTRAINT staff_invitations_office_fkey, DROP COLUMN job_title, "
        "DROP COLUMN display_name, DROP COLUMN offshore, DROP COLUMN access_ends_on, "
        "DROP COLUMN service_lines, DROP COLUMN team_ids, DROP COLUMN office_id, "
        "DROP COLUMN level, DROP COLUMN role_template"
    )
    op.execute(f"REVOKE UPDATE ({_MEMBER_UPDATES}) ON memberships FROM abacus_app")
    op.execute(
        "ALTER TABLE memberships DROP CONSTRAINT memberships_client_has_no_template, "
        "DROP COLUMN version, DROP COLUMN revoked_on_behalf_of, DROP COLUMN revoked_reason, "
        "DROP COLUMN access_ends_on, DROP COLUMN role_template"
    )
