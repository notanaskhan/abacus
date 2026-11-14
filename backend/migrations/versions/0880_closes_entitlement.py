"""C-01-T02 (C-01 §4.8; ADR P-28, DEC-55): `closes` joins a firm's modules.

The close engine (SPEC-655; CLS-01 to CLS-10, POR-11) is a module entitlement; `closes.engine`,
`closes.portal_requests`, `closes.agent` and `connections.ledger_sync` carry rollout only. No
firm holds it yet (dark), so nothing is backfilled. Expand only.

Revision ID: 0880
Revises: 0871
"""

from __future__ import annotations

from alembic import op

revision = "0880"
down_revision = "0871"
branch_labels = None
depends_on = None

_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion', 'tax_entity_returns')"
)
_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion', 'tax_entity_returns', "
    "'closes')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_NEW})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE module = 'closes'")
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_OLD})"
    )
