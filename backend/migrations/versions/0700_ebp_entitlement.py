"""A-05-T49 (DEC-2603): `ebp_audits` joins a firm's modules (ADR-148, ADR P-28, DEC-55).

The EBP module is an entitlement; `ebp.modules` and its siblings carry rollout only. A firm with
`ebp.modules` on keeps its access through a row written here. For a firm that isn't synthetic the
row holds only once the EBP CPA memo is signed (`platform.entitlements`, read at request time, not
here). Expand only.

Revision ID: 0700
Revises: 0687
"""

from __future__ import annotations

from alembic import op

revision = "0700"
down_revision = "0687"
branch_labels = None
depends_on = None

_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns')"
)
_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_NEW})"
    )
    op.execute(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "SELECT DISTINCT tenant_id, 'ebp_audits', DATE '2000-01-01', 'A-05-T49' "
        "FROM feature_flag_states WHERE flag = 'ebp.modules' AND value = 'true' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE module = 'ebp_audits'")
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_OLD})"
    )
