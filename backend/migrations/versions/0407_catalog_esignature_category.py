"""The integration catalogue may hold an e-signature app (N-02-T18 install path; ADR-342;
TASK-2152; DEC-1279).

A firm's DocuSeal install is a `firm_integrations` row whose `catalog_key` references the
catalogue, and the catalogue's categories were the read connectors' only. Expand-only: the
category CHECK gains `esignature`. The row itself arrives through the operator's load like every
catalogue row (`abacus_tools.esign_install`, from its reviewed document), never from here.

Revision ID: 0407
Revises: 0406
"""

from __future__ import annotations

from alembic import op

revision = "0407"
down_revision = "0406"
branch_labels = None
depends_on = None

_READ = "'ledger', 'bank_feed', 'card_feed', 'sales', 'payroll', 'hr', 'ticketing', 'grc'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE integration_catalog DROP CONSTRAINT integration_catalog_category_check, "
        "ADD CONSTRAINT integration_catalog_category_check "
        f"CHECK (category IN ({_READ}, 'esignature'))"
    )


def downgrade() -> None:
    # Refused by Postgres while an `esignature` row exists (rows are never deleted by the load):
    # disconnect the installs and remove the row by hand first.
    op.execute(
        "ALTER TABLE integration_catalog DROP CONSTRAINT integration_catalog_category_check, "
        "ADD CONSTRAINT integration_catalog_category_check "
        f"CHECK (category IN ({_READ}))"
    )
