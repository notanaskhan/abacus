"""T-05-T04 (T-05 §2, F13; ADR P-28, DEC-55): `tax_entity_returns` joins a firm's modules.

The entity returns workspace is an entitlement with `requires_review`: for a firm that isn't
synthetic it holds only once the five CPA memos are signed (`platform.entitlements`'
`REVIEWED_MODULES`, read at request time, never here). `tax.entity_workspace`,
`tax.workbook_run` and `tax.entity_agents` carry rollout only. No firm holds it yet (dark), so
nothing is backfilled. Expand only.

Revision ID: 0801
Revises: 0800
"""

from __future__ import annotations

from alembic import op

revision = "0801"
down_revision = "0800"
branch_labels = None
depends_on = None

_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion')"
)
_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion', 'tax_entity_returns')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_NEW})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE module = 'tax_entity_returns'")
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_OLD})"
    )
