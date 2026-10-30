"""The consent lifecycle sweep's own event kinds (T-01-T16; T-01 §4.4 ConsentLifecycleSweep;
DEC-1354; P-38 expand-only).

`consent_events.kind` gains `expiring` (a signed consent within 30 days of expiry, raised once,
which is how the sweep stays idempotent) and `reconsent_required` (signed under material
provider terms the register no longer holds, flagged once). Existing rows are untouched.

Revision ID: 0463
Revises: 0462
"""

from __future__ import annotations

from alembic import op

revision = "0463"
down_revision = "0462"
branch_labels = None
depends_on = None

_KINDS = (
    "requested",
    "signer_signed",
    "signed",
    "recorded",
    "declined",
    "revoked",
    "expired",
    "superseded",
    "copy_delivered",
    "renewal_drafted",
)


def _check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{k}'" for k in kinds)
    op.execute("ALTER TABLE consent_events DROP CONSTRAINT consent_events_kind_check")
    op.execute(
        f"ALTER TABLE consent_events ADD CONSTRAINT consent_events_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


def upgrade() -> None:
    _check((*_KINDS, "expiring", "reconsent_required"))


def downgrade() -> None:
    _check(_KINDS)
