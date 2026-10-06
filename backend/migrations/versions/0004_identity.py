"""Firms, users, memberships and engagement members (ADR-002, ADR-023, ADR-027; TASK-007 design §2-3).

- `users` is global (one login across firms): the app role has no privileges on it; only
  `abacus_identity` reads it, to resolve a token's subject before a tenant is chosen.
- `firms`, `memberships` and `engagement_members` are tenant tables. The app may only read them
  for now; the tasks that add membership management grant what they need (`engagement_members`
  gains its FK to `engagements` in TASK-008).
- `abacus_identity` reads users, and of memberships and firms only the columns sign-in needs.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE firms (
            tenant_id uuid PRIMARY KEY,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    tenant_table(op, "firms")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON firms FROM abacus_app")

    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            idp_issuer text NOT NULL CHECK (length(idp_issuer) BETWEEN 1 AND 500),
            idp_subject text NOT NULL CHECK (length(idp_subject) BETWEEN 1 AND 255),
            email text NOT NULL CHECK (length(email) BETWEEN 3 AND 320),
            display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT users_identity UNIQUE (idp_issuer, idp_subject)
        )
        """
    )
    op.execute("REVOKE ALL ON users FROM abacus_app")

    op.execute(
        """
        CREATE TABLE memberships (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users (id),
            firm_role text NULL
                CHECK (firm_role IN ('firm_admin', 'practice_leader', 'quality_partner')),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            revoked_at timestamptz NULL,
            PRIMARY KEY (tenant_id, id),
            CONSTRAINT memberships_one_per_user UNIQUE (tenant_id, user_id),
            CONSTRAINT memberships_revoked_at CHECK ((status = 'revoked') = (revoked_at IS NOT NULL))
        )
        """
    )
    op.execute("CREATE INDEX memberships_user ON memberships (user_id)")
    tenant_table(op, "memberships")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON memberships FROM abacus_app")

    op.execute(
        """
        CREATE TABLE engagement_members (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            user_id uuid NOT NULL,
            role text NOT NULL
                CHECK (role IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, engagement_id, user_id),
            -- An engagement member is always a member of the same firm.
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX engagement_members_user ON engagement_members (tenant_id, user_id)")
    tenant_table(op, "engagement_members")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON engagement_members FROM abacus_app")

    # Sign-in (abacus_identity, BYPASSRLS): read users, and only what it needs of the rest.
    op.execute("GRANT SELECT ON users TO abacus_identity")
    op.execute(
        "GRANT SELECT (tenant_id, id, user_id, firm_role, status) ON memberships TO abacus_identity"
    )
    op.execute("GRANT SELECT (tenant_id, name) ON firms TO abacus_identity")


def downgrade() -> None:
    op.execute("DROP TABLE engagement_members")
    op.execute("DROP TABLE memberships")
    op.execute("DROP TABLE users")
    op.execute("DROP TABLE firms")
