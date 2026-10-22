"""Client record, contacts and engagement contact designations (F-03-T25; chapter 03 §4.2,
migration plan row "client_record_contacts"; DEC-62, DEC-63, DEC-128).

- `clients` (organisations) gains `kind`, `status`, `primary_office_id`,
  `relationship_partner_id`, `risk_tier`, `is_attest_client`, `portal_status` and
  `practice_mgmt_ref`. Set by update; insert stays id, tenant and name.
- `is_attest_client` is derived (DEC-128): the client has an engagement of the attest family
  (`engagements.gate_policy`) that is accepted, contracted, active, on hold or delivered. A
  SECURITY DEFINER trigger on `engagements` keeps it current on every insert and every change of
  status, type or client (so on `engagement.status_changed`); the app can't set it.
- `client_entities` gains `entity_type`, `fye_month_day`, `state_of_formation`, `plan_number`,
  `date_of_death` and `grantor_status`. **No TIN column**: taxpayer IDs arrive sealed (P-12).
- `contacts` (organisations): a client's people and third parties, email unique per client.
- `engagement_contacts` (engagements): a contact's designations on an engagement (DEC-63),
  insert-only.

Revision ID: 0082
Revises: 0081
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None

_CLIENT_COLUMNS = (
    "kind, status, primary_office_id, relationship_partner_id, risk_tier, portal_status, "
    "practice_mgmt_ref"
)
_ENTITY_COLUMNS = (
    "entity_type, fye_month_day, state_of_formation, plan_number, date_of_death, grantor_status"
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE clients
            ADD COLUMN kind text NULL
                CHECK (kind IN ('household', 'business', 'plan_sponsor', 'nonprofit',
                                'trust_family')),
            ADD COLUMN status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('prospect', 'active', 'inactive', 'former')),
            ADD COLUMN primary_office_id uuid NULL,
            ADD COLUMN relationship_partner_id uuid NULL,
            ADD COLUMN risk_tier text NULL CHECK (risk_tier IN ('low', 'moderate', 'high')),
            ADD COLUMN is_attest_client boolean NOT NULL DEFAULT false,
            ADD COLUMN portal_status text NOT NULL DEFAULT 'not_invited'
                CHECK (portal_status IN ('not_invited', 'invited', 'active')),
            ADD COLUMN practice_mgmt_ref text NULL
                CHECK (length(practice_mgmt_ref) BETWEEN 1 AND 80),
            ADD CONSTRAINT clients_office_fkey
                FOREIGN KEY (tenant_id, primary_office_id) REFERENCES offices (tenant_id, id),
            ADD CONSTRAINT clients_partner_fkey
                FOREIGN KEY (tenant_id, relationship_partner_id)
                REFERENCES memberships (tenant_id, user_id)
        """
    )
    op.execute(f"GRANT UPDATE ({_CLIENT_COLUMNS}) ON clients TO abacus_app")
    # The attest family (`engagements.gate_policy`) and the statuses in which a client is one
    # (DEC-128); a unit test holds every `e.type IN` and `e.status IN` list here to the code.
    op.execute(
        """
        CREATE FUNCTION refresh_attest_client() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_client uuid;
            v_attest boolean;
        BEGIN
            FOR v_client IN
                SELECT DISTINCT x FROM unnest(ARRAY[
                    NEW.client_id,
                    CASE WHEN TG_OP = 'UPDATE' THEN OLD.client_id END
                ]) AS x WHERE x IS NOT NULL
            LOOP
                SELECT EXISTS (
                    SELECT 1 FROM public.engagements e
                     WHERE e.tenant_id = NEW.tenant_id AND e.client_id = v_client
                       AND e.type IN ('fs_audit', 'ebp_audit', 'review',
                                      'agreed_upon_procedures', 'soc1', 'soc2', 'readiness',
                                      'internal_audit')
                       AND e.status IN ('accepted', 'contracted', 'active', 'on_hold',
                                        'delivered')
                ) INTO v_attest;
                UPDATE public.clients SET is_attest_client = v_attest
                 WHERE tenant_id = NEW.tenant_id AND id = v_client
                   AND is_attest_client IS DISTINCT FROM v_attest;
            END LOOP;
            RETURN NULL;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION refresh_attest_client() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION refresh_attest_client() TO abacus_app")
    op.execute(
        "CREATE TRIGGER engagements_refresh_attest_client "
        "AFTER INSERT OR UPDATE OF status, type, client_id ON engagements "
        "FOR EACH ROW EXECUTE FUNCTION refresh_attest_client()"
    )
    # Backfill (synthetic data only, P-38): the owner is held to row-level security too, so the
    # two tables read are unforced for the statement, as 0068 does.
    for table in ("clients", "engagements"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE clients c SET is_attest_client = EXISTS (
            SELECT 1 FROM engagements e
             WHERE e.tenant_id = c.tenant_id AND e.client_id = c.id
               AND e.type IN ('fs_audit', 'ebp_audit', 'review', 'agreed_upon_procedures',
                              'soc1', 'soc2', 'readiness', 'internal_audit')
               AND e.status IN ('accepted', 'contracted', 'active', 'on_hold', 'delivered')
        )
        """
    )
    for table in ("clients", "engagements"):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        ALTER TABLE client_entities
            ADD COLUMN entity_type text NULL
                CHECK (entity_type IN ('individual', 'household_mfj', 'c_corp', 's_corp', 'llc',
                                       'partnership', 'trust', 'estate', 'ebp_plan',
                                       'exempt_org')),
            ADD COLUMN fye_month_day text NULL
                CHECK (fye_month_day ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
            ADD COLUMN state_of_formation text NULL CHECK (state_of_formation ~ '^[A-Z]{2}$'),
            ADD COLUMN plan_number text NULL CHECK (plan_number ~ '^[0-9]{3}$'),
            ADD COLUMN date_of_death date NULL,
            ADD COLUMN grantor_status boolean NULL
        """
    )
    op.execute(f"GRANT UPDATE ({_ENTITY_COLUMNS}) ON client_entities TO abacus_app")

    op.execute(
        """
        CREATE TABLE contacts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
            email text NULL CHECK (email ~ '^[^@[:space:]]+@[^@[:space:]]+$'),
            phone text NULL CHECK (length(phone) BETWEEN 1 AND 40),
            title text NULL CHECK (length(title) BETWEEN 1 AND 120),
            organisation_name text NULL CHECK (length(organisation_name) BETWEEN 1 AND 200),
            contact_kind text NOT NULL
                CHECK (contact_kind IN ('client_person', 'third_party', 'k1_recipient', 'tcwg',
                                        'component_auditor', 'prospect')),
            user_id uuid NULL REFERENCES users (id),
            portal_state text NOT NULL DEFAULT 'not_invited'
                CHECK (portal_state IN ('not_invited', 'invited', 'active', 'locked')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX contacts_one_email ON contacts (tenant_id, client_id, lower(email)) "
        "WHERE email IS NOT NULL"
    )
    tenant_table(op, "contacts")
    op.execute("REVOKE UPDATE, DELETE ON contacts FROM abacus_app")
    insert_columns(
        op,
        "contacts",
        (
            *("id", "tenant_id", "client_id", "display_name", "email", "phone", "title"),
            *("organisation_name", "contact_kind"),
        ),
    )
    op.execute(
        "GRANT UPDATE (display_name, phone, title, organisation_name, user_id, portal_state) "
        "ON contacts TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE engagement_contacts (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            designation text NOT NULL
                CHECK (designation IN ('approver_of_record', 'ske_designee', 'signing_officer',
                                       'plan_administrator', 'tcwg_member', 'primary_contact')),
            designated_by uuid NOT NULL,
            designated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, engagement_id, contact_id, designation),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    tenant_table(op, "engagement_contacts")
    op.execute("REVOKE UPDATE, DELETE ON engagement_contacts FROM abacus_app")
    insert_columns(
        op,
        "engagement_contacts",
        ("tenant_id", "engagement_id", "contact_id", "designation", "designated_by"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE engagement_contacts")
    op.execute("DROP TABLE contacts")
    op.execute(f"REVOKE UPDATE ({_ENTITY_COLUMNS}) ON client_entities FROM abacus_app")
    op.execute(
        "ALTER TABLE client_entities DROP COLUMN grantor_status, DROP COLUMN date_of_death, "
        "DROP COLUMN plan_number, DROP COLUMN state_of_formation, DROP COLUMN fye_month_day, "
        "DROP COLUMN entity_type"
    )
    op.execute("DROP TRIGGER engagements_refresh_attest_client ON engagements")
    op.execute("DROP FUNCTION refresh_attest_client()")
    op.execute(f"REVOKE UPDATE ({_CLIENT_COLUMNS}) ON clients FROM abacus_app")
    op.execute(
        "ALTER TABLE clients DROP CONSTRAINT clients_partner_fkey, "
        "DROP CONSTRAINT clients_office_fkey, DROP COLUMN practice_mgmt_ref, "
        "DROP COLUMN portal_status, DROP COLUMN is_attest_client, DROP COLUMN risk_tier, "
        "DROP COLUMN relationship_partner_id, DROP COLUMN primary_office_id, DROP COLUMN status, "
        "DROP COLUMN kind"
    )
