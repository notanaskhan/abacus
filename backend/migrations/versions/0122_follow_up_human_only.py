"""A follow-up is sent by a person (P-06-T14; DEC-74; I-AGENT-NEVER at the data layer).

`abacus_human_only_actions()` gains `follow_up.sent` (verb send), as
`docs/architecture/human-only-actions.yaml` now lists it: the `audit_events_human_only` trigger
(0097) refuses it from an `agent` or `policy` actor, whatever the permission matrix says.
`CREATE OR REPLACE` keeps the trigger and the app role's EXECUTE grant (0098).

Revision ID: 0122
Revises: 0121
"""

from __future__ import annotations

from alembic import op

revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

_BEFORE = (
    "engagement.accepted",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.confirmed",
    "legal_hold.placed",
    "materiality.decided",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "review.decided",
    "review.released",
    "risk.approved",
    "sample.approved",
    "sign_off.recorded",
    "statement.approved",
)
_AFTER = tuple(sorted((*_BEFORE, "follow_up.sent")))


def _define(actions: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    _define(_AFTER)


def downgrade() -> None:
    _define(_BEFORE)
