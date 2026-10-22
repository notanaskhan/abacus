"""`/v1/me` v3 (P-01-T04; SHL-03).

- `memberships.job_title`: the line under a person's name (ADM-02).
- `memberships.default_office_filter_id`: the person's default office filter, in the same firm.
  Offices filter lists only and never restrict access (DEC-30). The app may update only this
  column, and only the caller's own row (identity's service).
- `firms.sandbox_of_firm_id`: inferred sandbox marker (P-01 R9), nullable and additive. PLT-01
  (G-04) owns provisioning and may replace it before any sandbox exists. `firms.region` is
  already present (0086).

Revision ID: 0091
Revises: 0090
"""

from __future__ import annotations

from alembic import op

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE memberships
            ADD COLUMN job_title text NULL CHECK (length(job_title) BETWEEN 1 AND 120),
            ADD COLUMN default_office_filter_id uuid NULL,
            ADD CONSTRAINT memberships_default_office_fkey
                FOREIGN KEY (tenant_id, default_office_filter_id)
                REFERENCES offices (tenant_id, id)
        """
    )
    op.execute("GRANT UPDATE (default_office_filter_id) ON memberships TO abacus_app")
    op.execute(
        "ALTER TABLE firms ADD COLUMN sandbox_of_firm_id uuid NULL "
        "REFERENCES firms (tenant_id) CHECK (sandbox_of_firm_id <> tenant_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE firms DROP COLUMN sandbox_of_firm_id")
    op.execute("REVOKE UPDATE (default_office_filter_id) ON memberships FROM abacus_app")
    op.execute(
        "ALTER TABLE memberships DROP CONSTRAINT memberships_default_office_fkey, "
        "DROP COLUMN default_office_filter_id, DROP COLUMN job_title"
    )
