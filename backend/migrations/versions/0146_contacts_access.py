"""P-07-T25 (M3): contacts and portal access live (SPEC-321 Story 6; P-07 §4.2 M3; DEC-300).

- `contact_roles` (new, tenant): a contact's roles per entity (`scope_kind` client or
  client_entity), the 13 M3 codes; replaced as a set (insert and delete, never updated).
- `contacts` + `party_kind` (person, organisation, group) and `version` (the drawer's
  `seen_version`); the app may now also update `email`, `party_kind` and `version`.
- `contact_group_members` (new, tenant): who a group contact stands for.
- `client_invitations` + `grant_ids` (the pending grants a contact invitation activates; never
  with a grant template) and `used_at` (stamped when accepted: single use). The engagement stays
  required: a contact invitation names the one engagement its grants lie in, or (client-wide
  grants only) the client's engagement that met G1 (DEC-300).
- `client_access_grants.user_id` may be NULL while a grant is `pending` (or was revoked before
  anyone accepted): a pending grant waits for its contact's first sign-in. The app may set
  `user_id` once, only from NULL on a pending grant as it becomes active (trigger
  `client_access_grants_bind`). 0084's client-membership check (`client_access_grants_kind`)
  now skips a grant with no person and runs again when its person is set.
- Definers `portal_sign_in_unlock` (clear the firm's sign-in lock for one address: P-08's code
  and second-step lockouts share `sign_in_locks`) and `portal_sign_in_locked` (which of a list of
  addresses are locked now), both in the session's firm only (`app.tenant_id`).

Revision ID: 0146
Revises: 0143
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0146"
down_revision = "0143"
branch_labels = None
depends_on = None

_ROLES = (
    "'owner', 'cfo', 'controller', 'trustee', 'executor', 'taxpayer', 'spouse', "
    "'plan_sponsor_officer', 'recordkeeper', 'tpa', 'custodian', 'payroll_provider', 'other'"
)
_CONTACT_INSERT_V1 = (
    *("id", "tenant_id", "client_id", "display_name", "email", "phone", "title"),
    *("organisation_name", "contact_kind"),
)
_CONTACT_UPDATE_V1 = "display_name, phone, title, organisation_name, user_id, portal_state"
_INVITATION_INSERT_V2 = (
    *("id", "tenant_id", "engagement_id", "email", "role", "invited_by", "expires_at"),
    *("kind", "contact_id", "grant_template", "terms_version", "terms_url"),
)
_FUNCTIONS = ("portal_sign_in_unlock(text)", "portal_sign_in_locked(text[])")
# 0084's check, with (upgrade) the pending grant that has no person yet left to activation.
_KIND_FUNCTION = """
    CREATE OR REPLACE FUNCTION client_access_grants_kind() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        IF {skip}NOT EXISTS (SELECT 1 FROM public.memberships m
                        WHERE m.tenant_id = NEW.tenant_id AND m.user_id = NEW.user_id
                          AND m.kind = 'client') THEN
            RAISE EXCEPTION 'a client access grant needs a client membership'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    # --- contacts ------------------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE contacts
            ADD COLUMN party_kind text NOT NULL DEFAULT 'person'
                CHECK (party_kind IN ('person', 'organisation', 'group')),
            ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1)
        """
    )
    insert_columns(op, "contacts", (*_CONTACT_INSERT_V1, "party_kind"))
    op.execute(
        f"GRANT UPDATE ({_CONTACT_UPDATE_V1}, email, party_kind, version) "
        "ON contacts TO abacus_app"
    )
    op.execute(
        f"""
        CREATE TABLE contact_roles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            scope_kind text NOT NULL CHECK (scope_kind IN ('client', 'client_entity')),
            scope_id uuid NOT NULL,
            role text NOT NULL CHECK (role IN ({_ROLES})),
            title_text text NULL CHECK (length(title_text) BETWEEN 1 AND 120),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, contact_id, scope_kind, scope_id, role),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "contact_roles")
    op.execute("REVOKE UPDATE ON contact_roles FROM abacus_app")
    insert_columns(
        op,
        "contact_roles",
        ("tenant_id", "contact_id", "scope_kind", "scope_id", "role", "title_text"),
    )
    op.execute(
        """
        CREATE TABLE contact_group_members (
            tenant_id uuid NOT NULL,
            group_contact_id uuid NOT NULL,
            member_contact_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, group_contact_id, member_contact_id),
            CHECK (group_contact_id <> member_contact_id),
            FOREIGN KEY (tenant_id, group_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, member_contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "contact_group_members")
    op.execute("REVOKE UPDATE ON contact_group_members FROM abacus_app")
    insert_columns(
        op, "contact_group_members", ("tenant_id", "group_contact_id", "member_contact_id")
    )

    # --- invitations ---------------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE client_invitations
            ADD COLUMN grant_ids uuid[] NULL,
            ADD COLUMN used_at timestamptz NULL,
            ADD CONSTRAINT client_invitations_grant_ids CHECK (
                grant_ids IS NULL OR (
                    cardinality(grant_ids) BETWEEN 1 AND 200
                    AND contact_id IS NOT NULL AND grant_template IS NULL)),
            ADD CONSTRAINT client_invitations_used CHECK (used_at IS NULL OR status = 'accepted')
        """
    )
    op.execute(
        "CREATE INDEX client_invitations_contact ON client_invitations "
        "(tenant_id, contact_id, created_at) WHERE contact_id IS NOT NULL"
    )
    insert_columns(op, "client_invitations", (*_INVITATION_INSERT_V2, "grant_ids"))
    op.execute("GRANT UPDATE (used_at, grant_ids) ON client_invitations TO abacus_app")

    # --- pending grants ------------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE client_access_grants
            ALTER COLUMN user_id DROP NOT NULL,
            ADD CONSTRAINT client_access_grants_pending CHECK (
                user_id IS NOT NULL
                OR (contact_id IS NOT NULL AND status IN ('pending', 'revoked')))
        """
    )
    op.execute(
        "CREATE INDEX client_access_grants_contact ON client_access_grants "
        "(tenant_id, contact_id) WHERE contact_id IS NOT NULL"
    )
    op.execute(
        """
        CREATE FUNCTION client_access_grants_bind() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.user_id IS DISTINCT FROM OLD.user_id AND NOT (
                OLD.user_id IS NULL AND OLD.status = 'pending' AND NEW.status = 'active'
                AND NEW.user_id IS NOT NULL) THEN
                RAISE EXCEPTION 'a grant''s person is set once, as a pending grant activates'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER client_access_grants_bind BEFORE UPDATE ON client_access_grants "
        "FOR EACH ROW EXECUTE FUNCTION client_access_grants_bind()"
    )
    op.execute("GRANT UPDATE (user_id) ON client_access_grants TO abacus_app")
    op.execute(_KIND_FUNCTION.format(skip="NEW.user_id IS NOT NULL AND "))
    op.execute("DROP TRIGGER client_access_grants_kind ON client_access_grants")
    op.execute(
        "CREATE TRIGGER client_access_grants_kind BEFORE INSERT OR UPDATE OF user_id "
        "ON client_access_grants FOR EACH ROW EXECUTE FUNCTION client_access_grants_kind()"
    )

    # --- portal locks (CLI-04 d) ---------------------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_unlock(p_email text) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant';
            END IF;
            UPDATE public.sign_in_locks SET attempts = 0, window_until = NULL,
                locked_until = NULL
             WHERE host_tenant_id = v_tenant
               AND email_sha256 = encode(sha256(convert_to(lower(trim(p_email)), 'UTF8')), 'hex')
               AND locked_until > clock_timestamp();
            RETURN FOUND;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION portal_sign_in_locked(p_emails text[]) RETURNS SETOF text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp
        SET statement_timeout = '5s' AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no tenant';
            END IF;
            IF cardinality(p_emails) > 500 THEN
                RAISE EXCEPTION 'too many addresses';
            END IF;
            RETURN QUERY
            SELECT DISTINCT lower(trim(e)) FROM unnest(p_emails) AS e
             WHERE EXISTS (
                SELECT 1 FROM public.sign_in_locks l
                 WHERE l.host_tenant_id = v_tenant
                   AND l.email_sha256 = encode(sha256(convert_to(lower(trim(e)), 'UTF8')), 'hex')
                   AND l.locked_until > clock_timestamp());
        END $$
        """
    )
    for function in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO abacus_app")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("REVOKE UPDATE (user_id) ON client_access_grants FROM abacus_app")
    op.execute("DROP TRIGGER client_access_grants_kind ON client_access_grants")
    op.execute(_KIND_FUNCTION.format(skip=""))
    op.execute(
        "CREATE TRIGGER client_access_grants_kind BEFORE INSERT ON client_access_grants "
        "FOR EACH ROW EXECUTE FUNCTION client_access_grants_kind()"
    )
    op.execute("DROP TRIGGER client_access_grants_bind ON client_access_grants")
    op.execute("DROP FUNCTION client_access_grants_bind()")
    op.execute("DROP INDEX client_access_grants_contact")
    # Synthetic data only (P-38): grants no one accepted go with the column's NULLs.
    op.execute("ALTER TABLE client_access_grants NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_access_events NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "DELETE FROM client_access_events e USING client_access_grants g "
        "WHERE e.grant_id = g.id AND g.user_id IS NULL"
    )
    op.execute("DELETE FROM client_access_grants WHERE user_id IS NULL")
    op.execute("ALTER TABLE client_access_events FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_access_grants FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE client_access_grants DROP CONSTRAINT client_access_grants_pending, "
        "ALTER COLUMN user_id SET NOT NULL"
    )
    op.execute("REVOKE UPDATE (used_at, grant_ids) ON client_invitations FROM abacus_app")
    insert_columns(op, "client_invitations", _INVITATION_INSERT_V2)
    op.execute("DROP INDEX client_invitations_contact")
    op.execute(
        "ALTER TABLE client_invitations DROP CONSTRAINT client_invitations_used, "
        "DROP CONSTRAINT client_invitations_grant_ids, DROP COLUMN used_at, "
        "DROP COLUMN grant_ids"
    )
    op.execute("DROP TABLE contact_group_members")
    op.execute("DROP TABLE contact_roles")
    op.execute("REVOKE UPDATE (email, party_kind, version) ON contacts FROM abacus_app")
    insert_columns(op, "contacts", _CONTACT_INSERT_V1)
    op.execute("ALTER TABLE contacts DROP COLUMN version, DROP COLUMN party_kind")
