"""A-06-T37 (DEC-2714): `assurance_completion` joins a firm's modules (ADR P-28, DEC-55).

A-06's completion family (AUD-15, AUD-16, AUD-17, AUD-20) becomes an entitlement and its two
rollout flags retire: `assurance.completion` and `adjustments.entries`. A firm with either flag on
keeps its access through a row written here. Expand only; the flag rows stay as history.

Revision ID: 0713
Revises: 0712
"""

from __future__ import annotations

from alembic import op

revision = "0713"
down_revision = "0712"
branch_labels = None
depends_on = None

_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits')"
)
_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_NEW})"
    )
    op.execute(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "SELECT DISTINCT tenant_id, 'assurance_completion', DATE '2000-01-01', 'A-06-T37' "
        "FROM feature_flag_states "
        "WHERE flag IN ('assurance.completion', 'adjustments.entries') AND value = 'true' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tenant_entitlements WHERE module = 'assurance_completion'")
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        f"ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_OLD})"
    )
