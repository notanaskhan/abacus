"""Methodology templates and the engagement's pinned version (SPEC-008; ADR-004, ADR-053).

A firm imports its methodology as immutable, numbered versions of a named template: audit areas,
standard request items per area, and account rules mapping ledger account ranges to areas. An
engagement is pinned to one version, once (`methodology_version_id`, null to a value), and its
request items are seeded from it with their retrievability tier.

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_TABLES = (
    "methodology_templates",
    "methodology_versions",
    "methodology_areas",
    "methodology_request_items",
    "methodology_account_rules",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE methodology_templates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, name),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            source_fingerprint text NOT NULL CHECK (source_fingerprint ~ '^[0-9a-f]{64}$'),
            imported_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_id, version),
            FOREIGN KEY (tenant_id, template_id) REFERENCES methodology_templates (tenant_id, id),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_areas (
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            code text NOT NULL CHECK (length(code) BETWEEN 1 AND 20),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
            position integer NOT NULL CHECK (position >= 0),
            PRIMARY KEY (tenant_id, version_id, code),
            UNIQUE (tenant_id, version_id, position),
            FOREIGN KEY (tenant_id, version_id) REFERENCES methodology_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_request_items (
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            area_code text NOT NULL,
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 2000),
            retrievability_tier text NOT NULL CHECK (retrievability_tier IN ('A','B','C','D','E')),
            position integer NOT NULL CHECK (position >= 0),
            PRIMARY KEY (tenant_id, version_id, position),
            FOREIGN KEY (tenant_id, version_id, area_code)
                REFERENCES methodology_areas (tenant_id, version_id, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE methodology_account_rules (
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            area_code text NOT NULL,
            account_from text NOT NULL CHECK (length(account_from) BETWEEN 1 AND 50),
            account_to text NOT NULL CHECK (length(account_to) BETWEEN 1 AND 50),
            position integer NOT NULL CHECK (position >= 0),
            PRIMARY KEY (tenant_id, version_id, position),
            CONSTRAINT methodology_account_rules_range CHECK (account_from <= account_to),
            FOREIGN KEY (tenant_id, version_id, area_code)
                REFERENCES methodology_areas (tenant_id, version_id, code)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        insert_only(op, table)
    insert_columns(op, "methodology_templates", ("id", "tenant_id", "name", "created_by"))
    insert_columns(
        op,
        "methodology_versions",
        ("id", "tenant_id", "template_id", "version", "source_fingerprint", "imported_by"),
    )
    insert_columns(
        op, "methodology_areas", ("tenant_id", "version_id", "code", "name", "position")
    )
    insert_columns(
        op,
        "methodology_request_items",
        ("tenant_id", "version_id", "area_code", "description", "retrievability_tier", "position"),
    )
    insert_columns(
        op,
        "methodology_account_rules",
        ("tenant_id", "version_id", "area_code", "account_from", "account_to", "position"),
    )
    # The engagement's pinned version: set once by the service, under the engagement's lock.
    op.execute("ALTER TABLE engagements ADD COLUMN methodology_version_id uuid")
    op.execute(
        "ALTER TABLE engagements ADD CONSTRAINT engagements_methodology_version_fkey "
        "FOREIGN KEY (tenant_id, methodology_version_id) "
        "REFERENCES methodology_versions (tenant_id, id)"
    )
    op.execute("GRANT UPDATE (methodology_version_id) ON engagements TO abacus_app")
    op.execute(
        "ALTER TABLE request_items ADD COLUMN retrievability_tier text "
        "CHECK (retrievability_tier IN ('A','B','C','D','E'))"
    )
    op.execute("GRANT INSERT (retrievability_tier) ON request_items TO abacus_app")


def downgrade() -> None:
    op.execute("REVOKE INSERT (retrievability_tier) ON request_items FROM abacus_app")
    op.execute("ALTER TABLE request_items DROP COLUMN retrievability_tier")
    op.execute("REVOKE UPDATE (methodology_version_id) ON engagements FROM abacus_app")
    op.execute("ALTER TABLE engagements DROP COLUMN methodology_version_id")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
