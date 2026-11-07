"""A-06-T29 (DEC-2615): `financial_statements` joins the layouts a generated version may name.

The FS document is composed by code from a statement version (C11's composed kind `fs_package`),
in a seventh, code-only layout; no template may choose it. The CHECK on
`generated_document_versions.layout_key` widens by that one key. Expand only.

Revision ID: 0701
Revises: 0700
"""

from __future__ import annotations

from alembic import op

revision = "0701"
down_revision = "0700"
branch_labels = None
depends_on = None

_TABLE = "generated_document_versions"
_CHECK = "generated_document_versions_layout_key_check"
_OLD = "('letter', 'consent_7216', 'report', 'notice_response', 'package', 'run_export')"
_NEW = (
    "('letter', 'consent_7216', 'report', 'notice_response', 'package', 'run_export', "
    "'financial_statements')"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CHECK}")
    op.execute(f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_CHECK} CHECK (layout_key IN {_NEW})")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CHECK}")
    op.execute(
        f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_CHECK} CHECK (layout_key IN {_OLD}) NOT VALID"
    )
