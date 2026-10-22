"""Minimal subtype tables for the four other work-item kinds (F-03-T22; chapter 03 §3.1; DEC-07).

- `tax_returns` (tax): one return per work item, its entity, form and tax year.
- `closes` (closes): one close per work item, a `YYYY-MM` period, one per engagement and period.
- `notices` (notices): a notice's code and when it was received.
- `advisory_projects` (engagements): a project's name.
Each references its work item within the same engagement and tenant. Minimal columns only: the
owning modules extend them, expand-only (R8). Insert-only for the app until their owners add
lifecycle columns.

Revision ID: 0089
Revises: 0088
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None

_FORMS = "('1040', '1041', '1065', '1120s', '1120', '990', '706', '709')"
_OWNED = (
    "tenant_id uuid NOT NULL, work_item_id uuid PRIMARY KEY, engagement_id uuid NOT NULL, "
    "created_at timestamptz NOT NULL DEFAULT abacus_now(), "
    "FOREIGN KEY (tenant_id, engagement_id, work_item_id) "
    "REFERENCES work_items (tenant_id, engagement_id, id)"
)


def _table(name: str, columns: str, insert: tuple[str, ...]) -> None:
    op.execute(f"CREATE TABLE {name} ({_OWNED}, {columns})")
    tenant_table(op, name)
    op.execute(f"REVOKE UPDATE, DELETE ON {name} FROM abacus_app")
    insert_columns(op, name, ("tenant_id", "work_item_id", "engagement_id", *insert))


def upgrade() -> None:
    _table(
        "tax_returns",
        "client_entity_id uuid NULL, "
        f"form text NOT NULL CHECK (form IN {_FORMS}), "
        "tax_year integer NOT NULL CHECK (tax_year BETWEEN 1990 AND 2100)",
        ("client_entity_id", "form", "tax_year"),
    )
    _table(
        "closes",
        "period text NOT NULL CHECK (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'), "
        "UNIQUE (tenant_id, engagement_id, period)",
        ("period",),
    )
    _table(
        "notices",
        "notice_code text NOT NULL CHECK (notice_code ~ '^[A-Z0-9-]{2,20}$'), "
        "received_on date NOT NULL",
        ("notice_code", "received_on"),
    )
    _table(
        "advisory_projects",
        "name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200)",
        ("name",),
    )


def downgrade() -> None:
    for name in ("advisory_projects", "notices", "closes", "tax_returns"):
        op.execute(f"DROP TABLE {name}")
