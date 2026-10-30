"""Envelopes may name DocuSeal as their provider (N-02-T18 rework; ADR-342; DEC-1276).

ADR-342 replaced DocuSign with DocuSeal behind the same port. Expand-only: `envelopes.provider`
gains `docuseal` and keeps `docusign`, since drafts made before ADR-342 hold it (DRAFT_PROVIDER
was `docusign`); a later contract step removes `docusign` once no row can hold it.

Revision ID: 0406
Revises: 0430
"""

from __future__ import annotations

from alembic import op

revision = "0406"
down_revision = "0430"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE envelopes DROP CONSTRAINT envelopes_provider_check, "
        "ADD CONSTRAINT envelopes_provider_check "
        "CHECK (provider IN ('docuseal', 'docusign', 'record', 'fake'))"
    )


def downgrade() -> None:
    # Refused by Postgres while any row holds `docuseal` (a provider never changes on a row, so
    # nothing is rewritten here): roll the code back first, then drop those drafts by hand.
    op.execute(
        "ALTER TABLE envelopes DROP CONSTRAINT envelopes_provider_check, "
        "ADD CONSTRAINT envelopes_provider_check "
        "CHECK (provider IN ('docusign', 'record', 'fake'))"
    )
