"""Q-03-T353 (S52; TASK-8805; A-09 OQ-9; ADR-045 as relaxed by A-09; red): contract step.

Drop `connections_one_live_ledger`, the per-connection "one live ledger per entity" index from
0195. Since 0897 the rule lives on `connection_entity_coverage` (`connection_coverage_one_live`,
kept in step with `connections.status` by a trigger), which also refuses a second live ledger for a
subsidiary a NetSuite OneWorld connection covers. Both indexes use the same liveness
(`status <> 'revoked'` ⇔ `live`), so no row the old index admitted is lost and no row it refused is
now admitted for the connection's own entity: every connection inserts a coverage row for its own
entity.

Index-only: the expand-only guard has no rule for indexes, and the PR carries the `contract-step`
label as A-09 OQ-9 asks (first train after the Oct 20, 2028 window, DEC-5800).

Downgrade recreates the index; it fails if two live ledgers per entity exist, which coverage
refuses, so it cannot.

Revision ID: 0990
Revises: 0987
"""

from __future__ import annotations

from alembic import op

revision = "0990"
down_revision = "0987"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS connections_one_live_ledger")


def downgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX connections_one_live_ledger ON connections "
        "(tenant_id, client_entity_id) WHERE status <> 'revoked' AND category = 'ledger'"
    )
