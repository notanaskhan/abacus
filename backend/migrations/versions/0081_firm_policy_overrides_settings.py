"""Firm policy overrides and firm setting values (F-03-T24; chapter 03 §4.4, migration plan row
"policy_overrides_settings"; DEC-38, DEC-127).

- `firm_setting_values` (identity): the value of each registered firm setting a matrix cell
  names as `firm_setting(<key>)`. Registered keys only (the CHECK mirrors
  `authz.matrix.FIRM_SETTING_KEYS`); no row means off. `version` counts the changes.
- `firm_policy_overrides` (identity): a firm's stricter-only change to one matrix cell. The only
  decision is `deny`: it can narrow any cell and widen none, and anything looser is refused by
  the writer and by this CHECK.

Rows are set by the admin screens, the operator CLI or the scenario loader, never here.

Revision ID: 0081
Revises: 0080
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None

_KEYS = (
    "('seniors_can_accept', 'seniors_can_create', 'seniors_can_publish', "
    "'client_service_can_publish', 'staff_can_accept_evidence')"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE firm_setting_values (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            key text NOT NULL CHECK (key IN {_KEYS}),
            value boolean NOT NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            set_by uuid NOT NULL,
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, key)
        )
        """
    )
    tenant_table(op, "firm_setting_values")
    op.execute("REVOKE DELETE ON firm_setting_values FROM abacus_app")
    insert_columns(op, "firm_setting_values", ("tenant_id", "key", "value", "set_by"))
    op.execute("REVOKE UPDATE ON firm_setting_values FROM abacus_app")
    op.execute(
        "GRANT UPDATE (value, version, set_by, set_at) ON firm_setting_values TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE firm_policy_overrides (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            action text NOT NULL CHECK (action ~ '^[a-z][a-z_]*\\.[a-z][a-z_]*$'),
            role text NOT NULL CHECK (role ~ '^[a-z][a-z_]*$'),
            decision text NOT NULL CHECK (decision = 'deny'),
            reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
            set_by uuid NOT NULL,
            set_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, action, role)
        )
        """
    )
    tenant_table(op, "firm_policy_overrides")
    op.execute("REVOKE UPDATE, DELETE ON firm_policy_overrides FROM abacus_app")
    insert_columns(
        op,
        "firm_policy_overrides",
        ("tenant_id", "action", "role", "decision", "reason", "set_by"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE firm_policy_overrides")
    op.execute("DROP TABLE firm_setting_values")
