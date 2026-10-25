"""GENERATED from docs/architecture/human-only-actions.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.human_only_actions
"""

from typing import Final

# Audit actions an agent or a policy may never write (I-AGENT-NEVER).
HUMAN_ONLY_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "assurance.phase_recorded",
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
        "independence.confirmed",
        "independence.declined",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
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
        "sign_off.recorded",
        "statement.approved",
        "team.approved",
    }
)
