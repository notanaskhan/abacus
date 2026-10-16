"""Usage records say which boundary basis allowed a real-model call (SPEC-036 §4.8; TASK-075).

`boundary_basis`: `synthetic` (a synthetic firm) or `client_data` (a real firm through the five
conditions); null on the fake route. `terms_version`: the provider terms register's fingerprint
(ADR-114) for `client_data`, else null. Insert-only, like the rest of the row.

Revision ID: 0055
Revises: 0054
"""

from __future__ import annotations

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usage_records "
        "ADD COLUMN boundary_basis text NULL "
        "CHECK (boundary_basis IN ('synthetic', 'client_data')), "
        "ADD COLUMN terms_version text NULL CHECK (terms_version ~ '^[0-9a-f]{64}$'), "
        "ADD CONSTRAINT usage_records_terms_for_client_data CHECK "
        "((boundary_basis = 'client_data') = (terms_version IS NOT NULL))"
    )
    op.execute("GRANT INSERT (boundary_basis, terms_version) ON usage_records TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (boundary_basis, terms_version) ON usage_records FROM abacus_app")
    op.execute(
        "ALTER TABLE usage_records DROP CONSTRAINT usage_records_terms_for_client_data, "
        "DROP COLUMN terms_version, DROP COLUMN boundary_basis"
    )
