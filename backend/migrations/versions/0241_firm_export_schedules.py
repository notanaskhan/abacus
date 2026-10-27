"""The firm export's monthly schedule (G-02-T19; SPEC-349 AC-25; DEC-72, DEC-623).

`firm_export_schedules` (tenant PK, forced RLS): one schedule per firm, monthly on the 1st at
02:00 in the firm's time zone (v1's one cadence, held by CHECKs). It runs only once a
`security_admin` and a partner have each approved it, two distinct people (the CHECK); any change
to its contents or its pause clears both approvals (the guard trigger), so a change always waits
for both again. Every write is a live person's own (`updated_by`, bound by the trigger), and an
approval names that same person (clearing one is a change's). `status` follows from the facts
(a CHECK): `active` only with both approvals and not paused. Never deleted by the app.

Revision ID: 0241
Revises: 0240
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0241"
down_revision = "0240"
branch_labels = None
depends_on = None

_UPDATES = (
    "time_zone, contents, paused, status, approved_security_by, approved_partner_by, version, "
    "updated_by, updated_at"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE firm_export_schedules (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            cadence text NOT NULL DEFAULT 'monthly' CHECK (cadence = 'monthly'),
            day_of_month smallint NOT NULL DEFAULT 1 CHECK (day_of_month = 1),
            local_time text NOT NULL DEFAULT '02:00' CHECK (local_time = '02:00'),
            time_zone text NOT NULL CHECK (char_length(time_zone) BETWEEN 1 AND 64),
            contents jsonb NOT NULL CHECK (
                jsonb_typeof(contents) = 'array' AND jsonb_array_length(contents) >= 1),
            paused boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'pending_approval'
                CHECK (status IN ('pending_approval', 'active', 'paused')),
            approved_security_by uuid NULL,
            approved_partner_by uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT firm_export_schedules_two_people
                CHECK (approved_security_by IS DISTINCT FROM approved_partner_by
                       OR approved_security_by IS NULL),
            CONSTRAINT firm_export_schedules_status CHECK (
                CASE status
                    WHEN 'paused' THEN paused
                    WHEN 'active' THEN NOT paused AND approved_security_by IS NOT NULL
                        AND approved_partner_by IS NOT NULL
                    ELSE NOT paused AND (approved_security_by IS NULL
                        OR approved_partner_by IS NULL)
                END)
        )
        """
    )
    tenant_table(op, "firm_export_schedules")
    insert_columns(
        op,
        "firm_export_schedules",
        ("tenant_id", "time_zone", "contents", "paused", "status", "updated_by"),
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON firm_export_schedules FROM abacus_app")
    op.execute(f"GRANT UPDATE ({_UPDATES}) ON firm_export_schedules TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION firm_export_schedules_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.updated_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'a firm export schedule is a live person''s own'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'INSERT' THEN
                NEW.approved_security_by := NULL;
                NEW.approved_partner_by := NULL;
            ELSIF NEW.contents IS DISTINCT FROM OLD.contents OR NEW.paused <> OLD.paused
                  OR NEW.time_zone IS DISTINCT FROM OLD.time_zone THEN
                NEW.approved_security_by := NULL;  -- a change waits for both again (AC-25)
                NEW.approved_partner_by := NULL;
            ELSE
                IF NEW.approved_security_by IS DISTINCT FROM OLD.approved_security_by
                   AND NEW.approved_security_by IS NOT NULL
                   AND (OLD.approved_security_by IS NOT NULL
                        OR NEW.approved_security_by IS DISTINCT FROM NEW.updated_by) THEN
                    RAISE EXCEPTION 'an approval is the approver''s own, given once'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF NEW.approved_partner_by IS DISTINCT FROM OLD.approved_partner_by
                   AND NEW.approved_partner_by IS NOT NULL
                   AND (OLD.approved_partner_by IS NOT NULL
                        OR NEW.approved_partner_by IS DISTINCT FROM NEW.updated_by) THEN
                    RAISE EXCEPTION 'an approval is the approver''s own, given once'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            END IF;
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_export_schedules_guard BEFORE INSERT OR UPDATE "
        "ON firm_export_schedules FOR EACH ROW EXECUTE FUNCTION firm_export_schedules_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE firm_export_schedules")
    op.execute("DROP FUNCTION firm_export_schedules_guard()")
