"""A 1099 vendor's payments can be rents (C-02-T45, TASK-9003; C-02 F9 US-9.1; DEC-6009).

CLS-13 reports Larimer Street Properties on 1099-MISC box 1 (rents). The ledger's vendor feed
(C-02-T26: BillPayment and Purchase with the payment method) carries no expense category, so
whether a vendor's payments are rents is the vendor's classification, set by a person in the
drawer (`PATCH /v1/vendors/{id}`, `vendor_1099.update`) beside the entity type and the attorney
flag. `paid_rents` makes the reportability engine use 1099-MISC box 1; it never makes a vendor
reportable on its own (the threshold and the corporation exemption still apply).
"""

from __future__ import annotations

from alembic import op

revision = "1032"
down_revision = "1031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE vendors_1099 ADD COLUMN paid_rents boolean NOT NULL DEFAULT false")
    op.execute("GRANT UPDATE (paid_rents) ON vendors_1099 TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (paid_rents) ON vendors_1099 FROM abacus_app")
    op.execute("ALTER TABLE vendors_1099 DROP COLUMN paid_rents")
