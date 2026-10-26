"""One password unlock per evidence version (P-03-T19 security review L1; DEC-425). Expand-only.

Two people unlocking the same version at once each held only their own advisory lock, so both
could write a derivation. A partial unique index allows one `password_unlock` derivation per
version; the unlock service answers the loser 409 `not_password_protected`, as it answers any
unlock of a version already unlocked. `evidence_derivations` is new in 0109 and written only by
the unlock (P-03-T19), so no existing rows can collide.

`down_revision` is 0172 on this branch (S10 wave B); the merge re-points it after the other
branches' migrations.

Revision ID: 0173
Revises: 0172
"""

from __future__ import annotations

from alembic import op

revision = "0173"
down_revision = "0172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS evidence_derivations_one_unlock "
        "ON evidence_derivations (tenant_id, evidence_version_id) "
        "WHERE kind = 'password_unlock'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS evidence_derivations_one_unlock")
