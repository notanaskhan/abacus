"""A-05 workpapers EBP kinds (A-05-T09; A-05 §4.1; SPEC-641; DEC-1954): expand-only.

`workpapers.kind` admits the nine EBP designed workpapers (EBP-01 to EBP-09) beside A-04's four
planning kinds. Widening a CHECK is additive; no row changes.

Revision ID: 0641
Revises: 0640
"""

from __future__ import annotations

from alembic import op

revision = "0641"
down_revision = "0640"
branch_labels = None
depends_on = None

_PLANNING = (
    "general_audit_planning",
    "risk_assessment",
    "internal_control",
    "service_organizations",
)
_EBP = (
    "ebp_plan",
    "ebp_provisions",
    "ebp_eligibility",
    "ebp_contributions",
    "ebp_distributions_loans",
    "ebp_investments",
    "ebp_form5500",
    "ebp_participant_accounts",
    "ebp_admin_expenses",
)


def _check(kinds: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{k}'" for k in kinds)
    return f"CHECK (kind IN ({listed}))"


def upgrade() -> None:
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_kind_check")
    op.execute(
        f"ALTER TABLE workpapers ADD CONSTRAINT workpapers_kind_check {_check(_PLANNING + _EBP)}"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_kind_check")
    op.execute(f"ALTER TABLE workpapers ADD CONSTRAINT workpapers_kind_check {_check(_PLANNING)}")
