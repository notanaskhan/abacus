"""Q-05-T16 part 2 (S52; TASK-8821; SPEC-711 AC-10; OQ-5; red): firm-scope decision cards.

`decision_cards` gains `scope_kind` (`engagement`, the default, or `firm`); a firm card has no
engagement and no work item and names its decider (`reserved_role = qm_ultimate` with
`reserved_user_id`, the QM owner): the annual evaluation (`qm_annual_evaluation`) is Margaret's
alone. `engagement_id` drops NOT NULL only for firm cards (CHECK). Expand-only (a NOT NULL is
relaxed, a CHECK list grows).

Revision ID: 0996
Revises: 0995
"""

from __future__ import annotations

from alembic import op

revision = "0996"
down_revision = "0995"
branch_labels = None
depends_on = None

_OLD = "('engagement_partner', 'manager', 'eqr_reviewer', 'signer')"
_NEW = "('engagement_partner', 'manager', 'eqr_reviewer', 'signer', 'qm_ultimate')"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE decision_cards ADD COLUMN scope_kind text NOT NULL DEFAULT 'engagement' "
        "CHECK (scope_kind IN ('engagement', 'firm'))"
    )
    op.execute("GRANT INSERT (scope_kind) ON decision_cards TO abacus_app")
    op.execute("ALTER TABLE decision_cards ALTER COLUMN engagement_id DROP NOT NULL")
    op.execute("ALTER TABLE decision_cards DROP CONSTRAINT decision_cards_reserved_role_check")
    op.execute(
        "ALTER TABLE decision_cards ADD CONSTRAINT decision_cards_reserved_role_check "
        f"CHECK (reserved_role IN {_NEW})"
    )
    op.execute(
        "ALTER TABLE decision_cards ADD CONSTRAINT decision_cards_firm_scope CHECK ("
        "(scope_kind = 'firm') = (engagement_id IS NULL) AND "
        "(scope_kind <> 'firm' OR (work_item_id IS NULL AND reserved_role = 'qm_ultimate' "
        "AND reserved_user_id IS NOT NULL)) AND "
        "(reserved_role <> 'qm_ultimate' OR scope_kind = 'firm'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM decision_cards WHERE scope_kind = 'firm'")
    op.execute("ALTER TABLE decision_cards DROP CONSTRAINT decision_cards_firm_scope")
    op.execute("ALTER TABLE decision_cards DROP CONSTRAINT decision_cards_reserved_role_check")
    op.execute(
        "ALTER TABLE decision_cards ADD CONSTRAINT decision_cards_reserved_role_check "
        f"CHECK (reserved_role IN {_OLD})"
    )
    op.execute("ALTER TABLE decision_cards ALTER COLUMN engagement_id SET NOT NULL")
    op.execute("ALTER TABLE decision_cards DROP COLUMN scope_kind")
