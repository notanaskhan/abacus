"""Human-only audit actions for the A-06 decisions and the attribute grid (A-06-T16; I-AGENT-NEVER
at the data layer; ADR-005; DEC-2216). Expand-only.

`deficiency.concluded`, `sum.concluded` (the engagement partner's decision applied in the
decider's unit of work, A-06-T13) and `attribute_result.marked` (a person's mark on the shared
grid, A-05-T22) join `abacus_human_only_actions()`, so the `audit_events_human_only` trigger
refuses them with actor_kind `agent` or `policy`. The downgrade restores 0569's list.

Revision ID: 0661
Revises: 0660
"""

from __future__ import annotations

from alembic import op

revision = "0661"
down_revision = "0660"
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
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
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
    "team.approved",
    "transmission.recorded",
]
_HUMAN_ONLY = sorted(
    [*_BEFORE, "attribute_result.marked", "deficiency.concluded", "sum.concluded"]
)


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
