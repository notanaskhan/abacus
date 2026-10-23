"""P-08-T13: portal preferences for every grant scope kind.

0111 limited `portal_preferences.scope_kind` to `engagement`, `client` and `firm`, but a home is for
one grant's scope, and a full-client grant may name a client entity or a work item too (F-03-T26
`ScopeKind`). The check now takes the grant scope kinds; no row changes.

Revision ID: 0115
Revises: 0114
"""

from __future__ import annotations

from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None

_KINDS = (
    "('client', 'client_entity', 'engagement', 'work_item', 'request_item', 'k1_package', "
    "'governance_room', 'component', 'intake', 'firm')"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE portal_preferences DROP CONSTRAINT portal_preferences_scope_kind_check"
    )
    op.execute(
        "ALTER TABLE portal_preferences ADD CONSTRAINT portal_preferences_scope_kind_check "
        f"CHECK (scope_kind IN {_KINDS})"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE portal_preferences DROP CONSTRAINT portal_preferences_scope_kind_check"
    )
    op.execute(
        "ALTER TABLE portal_preferences ADD CONSTRAINT portal_preferences_scope_kind_check "
        "CHECK (scope_kind IN ('engagement', 'client', 'firm'))"
    )
