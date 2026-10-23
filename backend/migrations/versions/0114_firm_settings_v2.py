"""The typed firm-settings store (G-01-T04; G-01 section 4.2; DEC-170).

- `firm_settings(tenant_id, section, key, value jsonb, updated_by, updated_at)`: one row per
  registered key a firm has set, keys accepted only when registered (the service; 422
  `unknown_setting`). A key another module owns (the portal display name and footer, the firm's
  time zone) is never stored here: its owner's accessor writes its own table, so there is one copy.
- `firm_settings_sections(tenant_id, section, version)`: one version per section, bumped by every
  save; a save names the version it read (409 `stale_version`).

F-03's boolean `firm_setting_values` (matrix `firm_setting(...)` cells) stays as it is.

Revision ID: 0114
Revises: 0113
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None

_SECTIONS = "('profile', 'defaults', 'plan', 'independence')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE firm_settings (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            section text NOT NULL CHECK (section IN {_SECTIONS}),
            key text NOT NULL CHECK (key ~ '^[a-z][a-z0-9_]{{1,62}}$'),
            value jsonb NOT NULL
                CHECK (jsonb_typeof(value) IN ('string', 'number', 'boolean', 'null')),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, section, key)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE firm_settings_sections (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            section text NOT NULL CHECK (section IN {_SECTIONS}),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, section)
        )
        """
    )
    for table in ("firm_settings", "firm_settings_sections"):
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE ON {table} FROM abacus_app")
    insert_columns(op, "firm_settings", ("tenant_id", "section", "key", "value", "updated_by"))
    op.execute("REVOKE UPDATE ON firm_settings FROM abacus_app")
    op.execute("GRANT UPDATE (value, updated_by, updated_at) ON firm_settings TO abacus_app")
    insert_columns(op, "firm_settings_sections", ("tenant_id", "section"))
    op.execute("REVOKE UPDATE ON firm_settings_sections FROM abacus_app")
    op.execute("GRANT UPDATE (version, updated_at) ON firm_settings_sections TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE firm_settings_sections")
    op.execute("DROP TABLE firm_settings")
