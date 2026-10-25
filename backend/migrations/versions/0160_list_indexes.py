"""TASK-1250 (Q-03-T028 gaps, TASK-1245): the four composite indexes the plan tests found missing.

- `audit_events_target (tenant_id, target_type, target_id, seq)`: the activity feeds of a binder,
  a request and a wall read one target's events backwards, not the firm's whole log.
- `request_items_by_list (tenant_id, request_list_id, created_at, id) WHERE deleted_at IS NULL`:
  a binder's requests in order.
- `request_lists_portal (tenant_id, status, published_at)`: the portal's binder picker.
- `memberships_staff (tenant_id, kind, created_at, user_id)`: the staff roster.

Row-level security supplies `tenant_id` on every read, so each index leads with it. Created
inside the migration's transaction (not CONCURRENTLY): the tables are small on every
environment today; a large table would need a CONCURRENTLY migration of its own.

Revision ID: 0160
Revises: 0159
"""

from __future__ import annotations

from alembic import op

revision = "0160"
down_revision = "0159"
branch_labels = None
depends_on = None

_INDEXES = (
    "CREATE INDEX audit_events_target ON audit_events (tenant_id, target_type, target_id, seq)",
    "CREATE INDEX request_items_by_list ON request_items "
    "(tenant_id, request_list_id, created_at, id) WHERE deleted_at IS NULL",
    "CREATE INDEX request_lists_portal ON request_lists (tenant_id, status, published_at)",
    "CREATE INDEX memberships_staff ON memberships (tenant_id, kind, created_at, user_id)",
)
_NAMES = (
    "audit_events_target",
    "request_items_by_list",
    "request_lists_portal",
    "memberships_staff",
)


def upgrade() -> None:
    for statement in _INDEXES:
        op.execute(statement)


def downgrade() -> None:
    for name in _NAMES:
        op.execute(f"DROP INDEX {name}")
