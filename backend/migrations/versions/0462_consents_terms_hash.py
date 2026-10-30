"""A consent's provider-terms version holds the register's material-terms hash (T-01-T10; DEC-1353;
P-38 expand-only).

The consent gate (T-01-T11) compares a signed consent's `provider_terms_version` with the covering
Bedrock entry's `material` hash, a 64-character SHA-256, but 0402 capped the column at 40
characters. The CHECK widens to 64; nothing existing is touched (the only values written so far
are the fixtures' short versions, still valid).

Revision ID: 0462
Revises: 0461
"""

from __future__ import annotations

from alembic import op

revision = "0462"
down_revision = "0461"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE consents DROP CONSTRAINT consents_provider_terms_version_check")
    op.execute(
        "ALTER TABLE consents ADD CONSTRAINT consents_provider_terms_version_check "
        "CHECK (char_length(provider_terms_version) BETWEEN 1 AND 64)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE consents DROP CONSTRAINT consents_provider_terms_version_check")
    op.execute(
        "ALTER TABLE consents ADD CONSTRAINT consents_provider_terms_version_check "
        "CHECK (char_length(provider_terms_version) BETWEEN 1 AND 40)"
    )
