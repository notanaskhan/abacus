"""Offices, teams and membership attributes (F-03-T23; chapter 03 §4.2; DEC-30, Q-21).

- `offices`, `teams`, `team_rosters` (organisations): first-class offices, teams within an
  office or across offices, and a team's roster, one row per person ("team member" is not a code
  name, DEC-14). An office is a filter, never an access boundary (Q-21).
- `memberships` gains `level` (partner, manager, senior, staff, seasonal, admin), `office_id`,
  `service_lines`, `offshore` and `initials`.
- Firm role `security_admin`; engagement roles `eqr_reviewer`, `specialist` and `client_service`.
- `engagements.office_id` (added empty by 0069) now references `offices`.

Revision ID: 0080
Revises: 0079
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None

_FIRM_ROLES_BEFORE = "('firm_admin', 'practice_leader', 'quality_partner')"
_FIRM_ROLES = "('firm_admin', 'practice_leader', 'quality_partner', 'security_admin')"
_MEMBER_ROLES_BEFORE = (
    "('engagement_partner', 'manager', 'senior', 'staff', 'reviewer', "
    "'client_admin', 'client_contributor')"
)
_MEMBER_ROLES = (
    "('engagement_partner', 'manager', 'senior', 'staff', 'reviewer', "
    "'eqr_reviewer', 'specialist', 'client_service', 'client_admin', 'client_contributor')"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE offices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
            time_zone text NOT NULL DEFAULT 'America/Chicago'
                CHECK (time_zone ~ '^[A-Za-z]+(/[A-Za-z_+-]+){1,2}$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, name)
        )
        """
    )
    tenant_table(op, "offices")
    op.execute("REVOKE UPDATE, DELETE ON offices FROM abacus_app")
    insert_columns(op, "offices", ("tenant_id", "name", "time_zone"))

    op.execute(
        """
        CREATE TABLE teams (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            office_id uuid NULL,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, name),
            FOREIGN KEY (tenant_id, office_id) REFERENCES offices (tenant_id, id)
        )
        """
    )
    tenant_table(op, "teams")
    op.execute("REVOKE UPDATE, DELETE ON teams FROM abacus_app")
    insert_columns(op, "teams", ("tenant_id", "office_id", "name"))

    op.execute(
        """
        CREATE TABLE team_rosters (
            tenant_id uuid NOT NULL,
            team_id uuid NOT NULL,
            user_id uuid NOT NULL,
            added_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, team_id, user_id),
            FOREIGN KEY (tenant_id, team_id) REFERENCES teams (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "team_rosters")
    op.execute("REVOKE UPDATE ON team_rosters FROM abacus_app")
    insert_columns(op, "team_rosters", ("tenant_id", "team_id", "user_id"))

    op.execute(
        """
        ALTER TABLE memberships
            ADD COLUMN level text NULL
                CHECK (level IN ('partner', 'manager', 'senior', 'staff', 'seasonal', 'admin')),
            ADD COLUMN office_id uuid NULL,
            ADD COLUMN service_lines text[] NOT NULL DEFAULT '{}'
                CHECK (service_lines <@ ARRAY['audit', 'tax', 'cas', 'advisory']::text[]),
            ADD COLUMN offshore boolean NOT NULL DEFAULT false,
            ADD COLUMN initials text NULL CHECK (initials ~ '^[A-Z]{1,4}$'),
            ADD CONSTRAINT memberships_office_fkey
                FOREIGN KEY (tenant_id, office_id) REFERENCES offices (tenant_id, id),
            ADD CONSTRAINT memberships_client_has_no_level
                CHECK (kind = 'staff' OR (level IS NULL AND office_id IS NULL))
        """
    )
    op.execute("ALTER TABLE memberships DROP CONSTRAINT memberships_firm_role_check")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT memberships_firm_role_check "
        f"CHECK (firm_role IN {_FIRM_ROLES})"
    )
    op.execute("ALTER TABLE staff_invitations DROP CONSTRAINT staff_invitations_firm_role_check")
    op.execute(
        "ALTER TABLE staff_invitations ADD CONSTRAINT staff_invitations_firm_role_check "
        f"CHECK (firm_role IN {_FIRM_ROLES})"
    )
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        f"CHECK (role IN {_MEMBER_ROLES})"
    )
    op.execute(
        "ALTER TABLE engagements ADD CONSTRAINT engagements_office_fkey "
        "FOREIGN KEY (tenant_id, office_id) REFERENCES offices (tenant_id, id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE engagements DROP CONSTRAINT engagements_office_fkey")
    op.execute("ALTER TABLE engagement_members DROP CONSTRAINT engagement_members_role_check")
    op.execute(
        "ALTER TABLE engagement_members ADD CONSTRAINT engagement_members_role_check "
        f"CHECK (role IN {_MEMBER_ROLES_BEFORE})"
    )
    op.execute("ALTER TABLE staff_invitations DROP CONSTRAINT staff_invitations_firm_role_check")
    op.execute(
        "ALTER TABLE staff_invitations ADD CONSTRAINT staff_invitations_firm_role_check "
        f"CHECK (firm_role IN {_FIRM_ROLES_BEFORE})"
    )
    op.execute("ALTER TABLE memberships DROP CONSTRAINT memberships_firm_role_check")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT memberships_firm_role_check "
        f"CHECK (firm_role IN {_FIRM_ROLES_BEFORE})"
    )
    op.execute(
        "ALTER TABLE memberships DROP CONSTRAINT memberships_client_has_no_level, "
        "DROP CONSTRAINT memberships_office_fkey, DROP COLUMN initials, DROP COLUMN offshore, "
        "DROP COLUMN service_lines, DROP COLUMN office_id, DROP COLUMN level"
    )
    op.execute("DROP TABLE team_rosters")
    op.execute("DROP TABLE teams")
    op.execute("DROP TABLE offices")
