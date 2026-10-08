"""The identity role reads `memberships.kind` (fix for 0025; SPEC-015).

Sign-in resolves memberships through `abacus_identity`, which has column-level SELECT on
`memberships`. Migration 0025 added `kind` without granting it, so every account lookup failed.

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT (kind) ON memberships TO abacus_identity")


def downgrade() -> None:
    op.execute("REVOKE SELECT (kind) ON memberships FROM abacus_identity")
