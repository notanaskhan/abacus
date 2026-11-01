"""The EBP service provider's sealed EIN under the platform's sealed-identifier names (main CI
triage; DEC-1865; DEC-52, P-07-T07).

0610 named the columns `ein_sealed`, `ein_last4` and `ein_fp`; every other sealed taxpayer
identifier is `tin_sealed`, `tin_last4` and `tin_fingerprint`, and the schema test that no
plaintext identifier column exists reads those names only. Nothing reads the 0610 names yet
(the A-05 service lands later), so this renames them. Column grants and CHECKs follow a rename.

Revision ID: 0612
Revises: 0581
"""

from __future__ import annotations

from alembic import op

revision = "0612"
down_revision = "0581"
branch_labels = None
depends_on = None

_RENAMES = (
    ("ein_sealed", "tin_sealed"),
    ("ein_last4", "tin_last4"),
    ("ein_fp", "tin_fingerprint"),
)


def upgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER TABLE ebp_service_providers RENAME COLUMN {old} TO {new}")


def downgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f"ALTER TABLE ebp_service_providers RENAME COLUMN {new} TO {old}")
