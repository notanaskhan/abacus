"""The human-only list gains the AI policy's two verdicts (ED-180; G-02-T24; DEC-628).

`ai_policy.approved` and `ai_policy.declined` (a second partner approves or declines a published
version, AC-37) join `abacus_human_only_actions()`: the `audit_events_human_only` trigger refuses
either from an `agent` or `policy` actor, whatever the matrix says (I-AGENT-NEVER at the data
layer). 0212's 44 entries plus these two; the downgrade restores 0212's list. The review
lane's 0231 (P-04-T24) redefines the same function: whichever lands second redefines it with both
sets, and the register (`docs/architecture/human-only-actions.yaml`) holds every entry.

Revision ID: 0244
Revises: 0243
"""

from __future__ import annotations

from alembic import op

revision = "0244"
down_revision = "0243"
branch_labels = None
depends_on = None

_HUMAN_ONLY = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
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

_HUMAN_ONLY_0212 = [
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
    _human_only(_HUMAN_ONLY_0212)
