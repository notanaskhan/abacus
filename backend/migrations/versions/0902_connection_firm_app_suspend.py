"""W-01-T08 rest (TASK-8112; DEC-5083; SPEC-659 AC-25, OQ-5): a firm app's disable suspends.

Disabling a client-authorised firm app (QuickBooks Online) suspends every live client connection
of that provider in the firm: status `needs_attention` with the reason `firm_app_disabled`, read
as "Needs reauth" in closes and POR-16, and the sealed secret retired to the revocation queue so
the client re-authorises. Two CHECKs gain the value:

- `connections_status_reason_code_check` (0195): `firm_app_disabled` joins C20's reasons.
- `connection_grant_revocations_reason_check` (0215): a retired grant's reason.

Expand-only. Downgrade refuses while any row carries the new value (rows are never rewritten).

Revision ID: 0902
Revises: 0901
"""

from __future__ import annotations

from alembic import op

revision = "0902"
down_revision = "0901"
branch_labels = None
depends_on = None

_REASONS = "('token_expired', 'invalid_grant', 'sync_failed', 'provider_unavailable'"
_RETIRED = "('disconnected', 'replaced', 'abandoned'"


def _reason_check(values: str) -> None:
    op.execute(
        "ALTER TABLE connections DROP CONSTRAINT connections_status_reason_code_check, "
        "ADD CONSTRAINT connections_status_reason_code_check "
        f"CHECK (status_reason_code IN {values})"
    )


def _retired_check(values: str) -> None:
    op.execute(
        "ALTER TABLE connection_grant_revocations "
        "DROP CONSTRAINT connection_grant_revocations_reason_check, "
        f"ADD CONSTRAINT connection_grant_revocations_reason_check CHECK (reason IN {values})"
    )


def upgrade() -> None:
    _reason_check(f"{_REASONS}, 'firm_app_disabled')")
    _retired_check(f"{_RETIRED}, 'firm_app_disabled')")


def downgrade() -> None:
    _retired_check(f"{_RETIRED})")
    _reason_check(f"{_REASONS})")
