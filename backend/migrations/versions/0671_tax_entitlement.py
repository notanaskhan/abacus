"""T-03-T19 (DEC-2329): `tax_returns` joins a firm's modules (ADR-148, DEC-55).

`tax.returns_v1` and `tax.k1_release` retire, and this entitlement gates the same routes. A firm
with either flag on keeps its access through a row written here. Expand only.
"""

from __future__ import annotations

from alembic import op

revision = "0671"
down_revision = "0670"
branch_labels = None
depends_on = None

_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', 'insights')"
)
_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_NEW})"
    )
    op.execute(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "SELECT DISTINCT tenant_id, 'tax_returns', DATE '2000-01-01', 'T-03-T19' "
        "FROM feature_flag_states "
        "WHERE flag IN ('tax.returns_v1', 'tax.k1_release') AND value = 'true' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE module = 'tax_returns'")
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_OLD})"
    )
