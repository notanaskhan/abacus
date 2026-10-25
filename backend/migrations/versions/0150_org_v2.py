"""Offices, teams and groups v2 (G-01-T08; G-01 sections 3.7, 4.2; DEC-30, DEC-317).

- `offices` gains `code` (two to six capitals, unique per firm; back-filled from the name, its
  first three letters, then a fourth letter for a clash; an insert without one takes one by the
  same rule), `is_hq` (one per firm), an address,
  `lead_user_id`, `default_reviewer_pool_team_id` and `version`. The app may now update an
  office's descriptive columns; an office is still never deleted. An office stays a filter,
  never an access boundary (DEC-30): no authorisation rule reads any of this.
- `teams` gains `kind` (service_line, practice_group, eqr_pool, monitoring_reviewers,
  reviewer_pool, custom; existing teams are `custom`), `service_line` (set exactly for a
  `service_line` team), `lead_user_id` and `version`.
- `team_rosters` becomes insert-only history, the `work_item_assignments` shape: each change is
  a new row, a removal carries `removed_at`, and the roster is each person's latest row per team
  when it has none. Rows gain an id and an order (`seq`); who made each change is its audit
  row's actor.

Revision ID: 0150
Revises: 0146
"""

from __future__ import annotations

from alembic import op

revision = "0150"
down_revision = "0146"
branch_labels = None
depends_on = None

_KINDS = (
    "('service_line', 'practice_group', 'eqr_pool', 'monitoring_reviewers', 'reviewer_pool', "
    "'custom')"
)
_LINES = "('audit', 'tax', 'cas', 'advisory')"

# Each office's code from its name: its letters, upper-cased, the first three (padded with X);
# a second office whose three letters clash takes a fourth letter (B, C, ...) in creation order.
_BACKFILL_CODES = """
    WITH base AS (
        SELECT id, tenant_id, created_at,
               rpad(left(upper(regexp_replace(name, '[^A-Za-z]', '', 'g')), 3), 3, 'X') AS stem
          FROM offices
    ), ranked AS (
        SELECT id, stem,
               row_number() OVER (PARTITION BY tenant_id, stem ORDER BY created_at, id) AS n
          FROM base
    )
    UPDATE offices o
       SET code = CASE WHEN r.n = 1 THEN r.stem ELSE r.stem || chr(64 + r.n::int) END
      FROM ranked r
     WHERE o.id = r.id
"""

# An office inserted without a code (older callers, the scenario bootstrap) takes one by the same
# rule: its first three letters, or that and the first free fourth letter. Invoker rights, so it
# sees only the inserting firm's offices; a pinned search path, and no EXECUTE for PUBLIC (a
# trigger's function needs none to fire).
_DEFAULT_CODE = """
    CREATE FUNCTION offices_default_code() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE
        stem text := rpad(left(upper(regexp_replace(NEW.name, '[^A-Za-z]', '', 'g')), 3), 3, 'X');
        candidate text := stem;
        n integer := 1;
    BEGIN
        WHILE EXISTS (SELECT 1 FROM offices WHERE tenant_id = NEW.tenant_id AND code = candidate)
        LOOP
            n := n + 1;
            IF n > 26 THEN
                RAISE EXCEPTION 'no free office code for %', NEW.name
                    USING ERRCODE = 'unique_violation';
            END IF;
            candidate := stem || chr(64 + n);
        END LOOP;
        NEW.code := candidate;
        RETURN NEW;
    END
    $$
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE offices
            ADD COLUMN code text NULL,
            ADD COLUMN is_hq boolean NOT NULL DEFAULT false,
            ADD COLUMN address_line1 text NULL CHECK (length(address_line1) BETWEEN 1 AND 200),
            ADD COLUMN address_line2 text NULL CHECK (length(address_line2) BETWEEN 1 AND 200),
            ADD COLUMN city text NULL CHECK (length(city) BETWEEN 1 AND 120),
            ADD COLUMN region_code text NULL CHECK (region_code ~ '^[A-Z]{2,3}$'),
            ADD COLUMN postal_code text NULL CHECK (postal_code ~ '^[0-9A-Z -]{3,16}$'),
            ADD COLUMN lead_user_id uuid NULL,
            ADD COLUMN default_reviewer_pool_team_id uuid NULL,
            ADD COLUMN version integer NOT NULL DEFAULT 0
        """
    )
    op.execute(_BACKFILL_CODES)
    op.execute(
        """
        ALTER TABLE offices
            ALTER COLUMN code SET NOT NULL,
            ADD CONSTRAINT offices_code_format CHECK (code ~ '^[A-Z]{2,6}$'),
            ADD CONSTRAINT offices_code_unique UNIQUE (tenant_id, code),
            ADD CONSTRAINT offices_lead_fkey
                FOREIGN KEY (tenant_id, lead_user_id) REFERENCES memberships (tenant_id, user_id),
            ADD CONSTRAINT offices_reviewer_pool_fkey
                FOREIGN KEY (tenant_id, default_reviewer_pool_team_id)
                REFERENCES teams (tenant_id, id)
        """
    )
    op.execute("CREATE UNIQUE INDEX offices_one_hq ON offices (tenant_id) WHERE is_hq")
    op.execute(_DEFAULT_CODE)
    op.execute("REVOKE ALL ON FUNCTION offices_default_code() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER offices_default_code BEFORE INSERT ON offices "
        "FOR EACH ROW WHEN (NEW.code IS NULL) EXECUTE FUNCTION offices_default_code()"
    )
    op.execute(
        "GRANT INSERT (code, is_hq, address_line1, address_line2, city, region_code, "
        "postal_code, lead_user_id, default_reviewer_pool_team_id) ON offices TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (name, time_zone, code, is_hq, address_line1, address_line2, city, "
        "region_code, postal_code, lead_user_id, default_reviewer_pool_team_id, version) "
        "ON offices TO abacus_app"
    )

    op.execute(
        f"""
        ALTER TABLE teams
            ADD COLUMN kind text NOT NULL DEFAULT 'custom' CHECK (kind IN {_KINDS}),
            ADD COLUMN service_line text NULL CHECK (service_line IN {_LINES}),
            ADD COLUMN lead_user_id uuid NULL,
            ADD COLUMN version integer NOT NULL DEFAULT 0,
            ADD CONSTRAINT teams_service_line_kind
                CHECK ((kind = 'service_line') = (service_line IS NOT NULL)),
            ADD CONSTRAINT teams_lead_fkey
                FOREIGN KEY (tenant_id, lead_user_id) REFERENCES memberships (tenant_id, user_id)
        """
    )
    op.execute("GRANT INSERT (kind, service_line, lead_user_id) ON teams TO abacus_app")
    op.execute(
        "GRANT UPDATE (name, kind, service_line, office_id, lead_user_id, version) "
        "ON teams TO abacus_app"
    )

    op.execute(
        """
        ALTER TABLE team_rosters
            DROP CONSTRAINT team_rosters_pkey,
            ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid(),
            ADD COLUMN seq bigint GENERATED ALWAYS AS IDENTITY,
            ADD COLUMN removed_at timestamptz NULL,
            ADD PRIMARY KEY (id)
        """
    )
    op.execute(
        "CREATE INDEX team_rosters_latest ON team_rosters (tenant_id, team_id, user_id, seq DESC)"
    )
    op.execute("CREATE INDEX team_rosters_by_user ON team_rosters (tenant_id, user_id)")
    op.execute("REVOKE UPDATE, DELETE ON team_rosters FROM abacus_app")
    op.execute("GRANT INSERT (removed_at) ON team_rosters TO abacus_app")


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM team_rosters WHERE removed_at IS NOT NULL) THEN "
        "RAISE EXCEPTION 'refusing to downgrade: team roster history exists'; END IF; END $$"
    )
    op.execute("REVOKE INSERT (removed_at) ON team_rosters FROM abacus_app")
    op.execute("GRANT DELETE ON team_rosters TO abacus_app")
    op.execute("DROP INDEX team_rosters_by_user")
    op.execute("DROP INDEX team_rosters_latest")
    op.execute(
        "ALTER TABLE team_rosters DROP CONSTRAINT team_rosters_pkey, DROP COLUMN removed_at, "
        "DROP COLUMN seq, DROP COLUMN id"
    )
    op.execute("ALTER TABLE team_rosters ADD PRIMARY KEY (tenant_id, team_id, user_id)")

    op.execute(
        "REVOKE UPDATE (name, kind, service_line, office_id, lead_user_id, version) "
        "ON teams FROM abacus_app"
    )
    op.execute("REVOKE INSERT (kind, service_line, lead_user_id) ON teams FROM abacus_app")
    op.execute(
        "ALTER TABLE teams DROP CONSTRAINT teams_lead_fkey, "
        "DROP CONSTRAINT teams_service_line_kind, DROP COLUMN version, DROP COLUMN lead_user_id, "
        "DROP COLUMN service_line, DROP COLUMN kind"
    )

    op.execute(
        "REVOKE UPDATE (name, time_zone, code, is_hq, address_line1, address_line2, city, "
        "region_code, postal_code, lead_user_id, default_reviewer_pool_team_id, version) "
        "ON offices FROM abacus_app"
    )
    op.execute(
        "REVOKE INSERT (code, is_hq, address_line1, address_line2, city, region_code, "
        "postal_code, lead_user_id, default_reviewer_pool_team_id) ON offices FROM abacus_app"
    )
    op.execute("DROP TRIGGER offices_default_code ON offices")
    op.execute("DROP FUNCTION offices_default_code()")
    op.execute("DROP INDEX offices_one_hq")
    op.execute(
        "ALTER TABLE offices DROP CONSTRAINT offices_reviewer_pool_fkey, "
        "DROP CONSTRAINT offices_lead_fkey, DROP CONSTRAINT offices_code_unique, "
        "DROP CONSTRAINT offices_code_format, DROP COLUMN version, "
        "DROP COLUMN default_reviewer_pool_team_id, DROP COLUMN lead_user_id, "
        "DROP COLUMN postal_code, DROP COLUMN region_code, DROP COLUMN city, "
        "DROP COLUMN address_line2, DROP COLUMN address_line1, DROP COLUMN is_hq, "
        "DROP COLUMN code"
    )
