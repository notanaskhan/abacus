"""Access events (Q-02-T20; AC-23, AC-25), owned by `kernel.access`.

Reading client content leaves an identifier-only row: an evidence download, a page rendition or
preview, or a model context built from documents. No file name, quote or value.

- `access_events` is partitioned by month on `occurred_at`. Every partition has forced row-level
  security under the tenant policy and the insert-only trigger (cloned from the parent).
- The app inserts through the parent only. It holds no privilege on any partition, and it can
  never update or delete a row.
- A DEFAULT partition catches a month whose partition doesn't exist yet, so a write never fails
  because maintenance ran late.
- `access_events_partition(month)`, a SECURITY DEFINER function, creates one month's partition
  with the same protections. The monthly maintenance calls it ahead of time; this migration calls
  it for October 2026 through March 2027.

Revision ID: 0105
Revises: 0104
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None

_INSERT = (
    "tenant_id",
    "actor_kind",
    "actor_id",
    "on_behalf_of_user_id",
    "run_id",
    "kind",
    "subject_type",
    "subject_id",
    "client_id",
    "engagement_id",
    "work_item_id",
    "taxpayer_contact_id",
    "tax_year",
    "flags",
    "request_id",
)
_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_FIRST_MONTHS = (
    "2026-10-01",
    "2026-11-01",
    "2026-12-01",
    "2027-01-01",
    "2027-02-01",
    "2027-03-01",
)


# One partition's protections, as the definer applies them (and this migration, once).
_PROTECT = (
    "ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE {t} FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY tenant_isolation ON {{t}} USING (tenant_id = {_TENANT}) "
    f"WITH CHECK (tenant_id = {_TENANT})",
    "REVOKE ALL ON {t} FROM PUBLIC, abacus_app",
    "CREATE TRIGGER access_events_no_truncate BEFORE TRUNCATE ON {t} "
    "FOR EACH STATEMENT EXECUTE FUNCTION public.access_events_immutable()",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE access_events (
            tenant_id uuid NOT NULL,
            id bigint GENERATED ALWAYS AS IDENTITY,
            occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system', 'support')),
            actor_id uuid NULL,
            on_behalf_of_user_id uuid NULL,
            run_id uuid NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z_]+\\.[a-z_]+$'),
            subject_type text NOT NULL CHECK (subject_type ~ '^[a-z][a-z_]{0,39}$'),
            subject_id uuid NOT NULL,
            client_id uuid NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            taxpayer_contact_id uuid NULL,
            tax_year smallint NULL CHECK (tax_year BETWEEN 1990 AND 2100),
            flags text[] NOT NULL DEFAULT '{}' CHECK (flags <@ ARRAY['tri', 'phi', 'pii_tin',
                'pii_bank', 'pii_ip_pin', 'pii_dob', 'restricted']::text[]),
            request_id uuid NULL,
            PRIMARY KEY (tenant_id, occurred_at, id)
        ) PARTITION BY RANGE (occurred_at)
        """
    )
    op.execute(
        "CREATE INDEX access_events_by_subject ON access_events "
        "(tenant_id, subject_type, subject_id, occurred_at DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION access_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'access_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER access_events_immutable BEFORE UPDATE OR DELETE ON access_events "
        "FOR EACH ROW EXECUTE FUNCTION access_events_immutable()"
    )
    op.execute(
        "CREATE TRIGGER access_events_no_truncate BEFORE TRUNCATE ON access_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION access_events_immutable()"
    )
    tenant_table(op, "access_events")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON access_events FROM abacus_app")
    insert_columns(op, "access_events", _INSERT)

    op.execute("CREATE TABLE access_events_default PARTITION OF access_events DEFAULT")
    for statement in _PROTECT:
        op.execute(statement.format(t="access_events_default"))
    quoted = (statement.format(t="public.%1$I").replace("'", "''") for statement in _PROTECT)
    protect = "\n".join(f"            EXECUTE format('{sql}', v_name);" for sql in quoted)
    op.execute(
        f"""
        CREATE FUNCTION access_events_partition(p_month date) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_from date := date_trunc('month', p_month)::date;
            v_name text := format('access_events_%s', to_char(v_from, 'YYYY_MM'));
        BEGIN
            IF to_regclass(format('public.%I', v_name)) IS NOT NULL THEN
                RETURN v_name;
            END IF;
            EXECUTE format(
                'CREATE TABLE public.%I PARTITION OF public.access_events '
                'FOR VALUES FROM (%L) TO (%L)',
                v_name, v_from, (v_from + interval '1 month')::date
            );
{protect}
            RETURN v_name;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION access_events_partition(date) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION access_events_partition(date) TO abacus_app")
    for month in _FIRST_MONTHS:
        op.execute(f"SELECT access_events_partition(DATE '{month}')")


def downgrade() -> None:
    op.execute("DROP FUNCTION access_events_partition(date)")
    op.execute("DROP TABLE access_events")
    op.execute("DROP FUNCTION access_events_immutable()")
