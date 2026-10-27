"""The human-only list gains the proposal and suggestion verdicts (P-04-T24; DEC-601; TASK-1460).

`proposal.approved`, `proposal.approved_with_edits`, `proposal.rejected` and `proposal.routed` (a
person approves, rejects or sends on the agent's change set) and `suggestion.adopted`,
`suggestion.edited` and `suggestion.dismissed` (a person adopts or dismisses one suggested value)
join `abacus_human_only_actions()`: the `audit_events_human_only` trigger refuses any of them from
an `agent` or `policy` actor, whatever the matrix says (I-AGENT-NEVER at the data layer; ADR-161).
0212's 44 entries plus these seven; the downgrade restores 0212's list.

Revision ID: 0231
Revises: 0230
"""

from __future__ import annotations

from alembic import op

revision = "0231"
down_revision = "0230"
branch_labels = None
depends_on = None

_HUMAN_ONLY = [
    "acceptance.decided",
    "acceptance.review_completed",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
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
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
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
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]

# The list this migration follows in the merged chain: 0226's (S11 lane 8), 0212's 44 plus
# assurance.archive_recorded and assurance.release_recorded; the downgrade restores it.
_HUMAN_ONLY_0212 = [
    "acceptance.decided",
    "acceptance.review_completed",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
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
