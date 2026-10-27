"""The human-only list gains the decision card's two verdicts (P-04-T23; DEC-503; TASK-1402).

`decision.decided` (the reserved person decides a card) and `decision.reassessed` (No change, or
a superseding card) join `abacus_human_only_actions()`: the `audit_events_human_only` trigger
refuses either from an `agent` or `policy` actor, whatever the matrix says (I-AGENT-NEVER at the
data layer). 0175's 42 entries plus these two; the downgrade restores 0175's list.

Revision ID: 0212
Revises: 0211
"""

from __future__ import annotations

from alembic import op

revision = "0212"
down_revision = "0211"
branch_labels = None
depends_on = None

_HUMAN_ONLY = [
    "acceptance.decided",
    "acceptance.review_completed",
    "assurance.phase_recorded",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "materiality.decided",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "team.approved",
]

_HUMAN_ONLY_0175 = [
    "acceptance.decided",
    "acceptance.review_completed",
    "assurance.phase_recorded",
    "conflict.cleared",
    "contact.unlocked",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "materiality.decided",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "team.approved",
]


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0175)
