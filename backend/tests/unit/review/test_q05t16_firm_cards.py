"""Q-05-T16 part 2 (TASK-8821; SPEC-711 AC-10; OQ-5): firm-scope decision cards.

"Only Margaret Okonkwo can decide the evaluation card." Here: the matrix gives
`quality_evaluation.decide` to the QM owner only (never the agent, the system or a firm admin)
with fresh MFA; the service also requires the card's named person; the database ties a firm card
to `qm_ultimate` with a named person and no engagement (0996).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from abacus.modules.review import firm_cards

REPO = Path(__file__).resolve().parents[4]


def test_ac_only_the_qm_owner_decides_at_the_matrix() -> None:
    actions = yaml.safe_load((REPO / "docs/architecture/permission-matrix/practice.yaml").read_text())["actions"]
    row = actions["quality_evaluation.decide"]
    assert row["quality_partner"] == "allow" and row["firm_admin"] == "deny"
    assert row["agent"] == "deny" and row["system"] == "deny" and row["mfa_recent"] == "required"


def test_ac_the_service_requires_the_named_person() -> None:
    source = inspect.getsource(firm_cards.decide_firm_card)
    assert "card.reserved_user_id != ctx.user_id" in source
    assert 'actor_kind != "human"' in source


def test_the_database_ties_firm_cards_to_qm_ultimate() -> None:
    sql = (REPO / "backend/migrations/versions/0996_review_firm_scope_cards.py").read_text()
    assert "reserved_role = 'qm_ultimate' " in sql and "reserved_user_id IS NOT NULL" in sql
    assert "(scope_kind = 'firm') = (engagement_id IS NULL)" in sql
