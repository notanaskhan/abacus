"""A-01-T05 security review: recording an assurance phase is human-only (DEC-262; ADR-005).

The human-only register gains `assurance.phase_recorded` (a person records a phase in record
mode), so the `audit_events_human_only` trigger refuses it from an agent or a policy whatever the
matrix says. `assurance.phase_derived` stays off the list: it is written by the system from a
computed gate's `gate.met`, or by the person whose own release or archive met the gate.

`abacus_human_only_actions()` is redefined as main's current 27 entries (0132) plus this one; the
downgrade restores exactly those 27. Branches that add entries are unioned at merge.

Revision ID: 0135
Revises: 0134
"""

from __future__ import annotations

from alembic import op

revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None

# The register as 0132 left it (27 entries).
_HUMAN_ONLY_0132 = sorted(
    [
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
        "evidence.accepted",
        "firm.ai_client_data_opted_in",
        "firm_export.approved",
        "firm_export.declined",
        "follow_up.sent",
        "going_concern.decided",
        "guidance_draft.approved",
        "independence.confirmed",
        "independence.declined",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "risk.approved",
        "sample.approved",
        "sign_off.recorded",
        "statement.approved",
        "review_decision.created",
        "review_decision.undone",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0132, "assurance.phase_recorded"])


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
    _human_only(_HUMAN_ONLY_0132)
