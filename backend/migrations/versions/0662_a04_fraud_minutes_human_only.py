"""`fraud_minutes.approved` joins the human-only audit actions (A-04-T30; I-AGENT-NEVER at the data
layer; ADR-005; DEC-2223). Expand-only.

A-04-T19's engagement partner approval of the fraud brainstorming minutes is written as
`fraud_minutes.approved`; the matrix already refuses agent, system, support and staff, and now
the `audit_events_human_only` trigger refuses it with actor_kind `agent` or `policy` too. The
downgrade restores 0661's list.

Revision ID: 0662
Revises: 0661
"""

from __future__ import annotations

from alembic import op

revision = "0662"
down_revision = "0661"
branch_labels = None
depends_on = None

_BEFORE = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "attribute_result.marked",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "deficiency.concluded",
    "delivery_packet.approved",
    "efile_ack.recorded",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
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
    "letter.approved",
    "materiality.decided",
    "methodology_version.approved",
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
    "return.delivered",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "schedule_k_release.requested",
    "schedule_k_release.undone",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "sum.concluded",
    "team.approved",
    "transmission.recorded",
]
_HUMAN_ONLY = sorted([*_BEFORE, "fraud_minutes.approved"])


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
    _human_only(_BEFORE)
