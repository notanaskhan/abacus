"""ED-011: three SPEC-025 gate facts join the human-only register (Q-02-T17, INV-1).

`engagement.acceptance_recorded`, `engagement.letter_recorded` and `independence.declined` are
recorded by a person (SPEC-025 §14) but were missing from
`docs/architecture/human-only-actions.yaml`, so the `audit_events_human_only` trigger would have
accepted them written by an `agent` or `policy` actor. This redefines `abacus_human_only_actions()`
with the register as it now stands. `CREATE OR REPLACE` keeps 0098's EXECUTE grant to the app
role; the trigger reads the function on every insert, so it needs no change.

Revision ID: 0127
Revises: 0115
"""

from __future__ import annotations

from alembic import op

revision = "0127"
down_revision = "0115"
branch_labels = None
depends_on = None

_ACTIONS = """ARRAY[
        'engagement.acceptance_recorded',
        'engagement.accepted',
        'engagement.letter_recorded',
        'evidence.accepted',
        'firm.ai_client_data_opted_in',
        'firm_export.approved',
        'going_concern.decided',
        'guidance_draft.approved',
        'independence.confirmed',
        'independence.declined',
        'legal_hold.placed',
        'materiality.decided',
        'procedure.concluded',
        'report.approved',
        'report.released',
        'review.decided',
        'review.released',
        'risk.approved',
        'sample.approved',
        'sign_off.recorded',
        'statement.approved'
    ]::text[]"""

_BEFORE = """ARRAY[
        'engagement.accepted',
        'evidence.accepted',
        'firm.ai_client_data_opted_in',
        'firm_export.approved',
        'going_concern.decided',
        'guidance_draft.approved',
        'independence.confirmed',
        'legal_hold.placed',
        'materiality.decided',
        'procedure.concluded',
        'report.approved',
        'report.released',
        'review.decided',
        'review.released',
        'risk.approved',
        'sample.approved',
        'sign_off.recorded',
        'statement.approved'
    ]::text[]"""


def _define(actions: str) -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT {actions} $$"
    )


def upgrade() -> None:
    _define(_ACTIONS)


def downgrade() -> None:
    _define(_BEFORE)
