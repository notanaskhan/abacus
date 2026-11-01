"""The Methodology importer's runs (K-01-T21; K-01 §4.4; DEC-1856). Expand-only.

An engagement-less run was the guidance drafter's on a template version (0054) or the matcher's
on an intake attachment (0431). The Methodology importer's run is the third kind: firm-level,
before any version exists (the version is written by the finish step), so it names neither a
version nor an attachment. Only `methodology.importer` may write that shape.

Downgrade restores the 0431 check; it fails while an importer run exists, as it should.

Revision ID: 0611
Revises: 0610
"""

from __future__ import annotations

from alembic import op

_DRAFTER = "requests.guidance_drafter"
_MATCHER = "evidence.matcher"
_IMPORTER = "methodology.importer"

revision = "0611"
down_revision = "0610"
branch_labels = None
depends_on = None


def _check(*kinds: str) -> None:
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_firm_level")
    op.execute(
        "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_firm_level CHECK ("
        + " OR ".join(kinds)
        + ")"
    )


_ENGAGEMENT = (
    "(engagement_id IS NOT NULL AND methodology_version_id IS NULL "
    "AND inbox_attachment_id IS NULL)"
)
_DRAFTER_RUN = (
    "(engagement_id IS NULL AND methodology_version_id IS NOT NULL "
    f"AND inbox_attachment_id IS NULL AND agent_id = '{_DRAFTER}')"
)
_MATCHER_RUN = (
    "(engagement_id IS NULL AND methodology_version_id IS NULL "
    f"AND inbox_attachment_id IS NOT NULL AND agent_id = '{_MATCHER}')"
)
_IMPORTER_RUN = (
    "(engagement_id IS NULL AND methodology_version_id IS NULL "
    f"AND inbox_attachment_id IS NULL AND agent_id = '{_IMPORTER}')"
)


def upgrade() -> None:
    _check(_ENGAGEMENT, _DRAFTER_RUN, _MATCHER_RUN, _IMPORTER_RUN)


def downgrade() -> None:
    _check(_ENGAGEMENT, _DRAFTER_RUN, _MATCHER_RUN)
