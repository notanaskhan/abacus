"""T-07-T27 (TASK-8359; ADR-078): the rest of the row, written outside the implementing sessions.
ac-test-author: ayushkbhatia

- L4 values approval is the engagement partner's alone: the matrix's `sign_off.partner` allows
  only `engagement_partner`, and TXT-04's header offers "sign_off.l4" only to a viewer the
  matrix allows (the finding: the header listed every action for every viewer).
- The 65-day election and a trustee question's send are human-only: the agent and the system are
  denied both, and no client role may record the election.
- A draft K-1 never reaches the portal: T-02-T26's `drafts_never_list` and T-07-T28's isolation
  suite cover it against Postgres (the 1041's packages use the same `k1_documents`).
"""

from __future__ import annotations

import uuid
from functools import cache
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import estate_service

MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"
Rule = dict[str, str]


@cache
def _rules() -> dict[str, Rule]:
    out: dict[str, Rule] = {}
    for f in MATRIX.glob("*.yaml"):
        data = cast(dict[str, object], yaml.safe_load(f.read_text()) or {})
        out.update(cast(dict[str, Rule], data.get("actions") or {}))
    return out


def _allowed(action: str) -> set[str]:
    return {role for role, v in _rules()[action].items() if v == "allow"}


def test_l4_values_approval_is_the_engagement_partners_alone() -> None:
    assert _allowed("sign_off.partner") == {"engagement_partner"}
    assert _rules()["sign_off.partner"].get("agent") == "deny"


@pytest.mark.parametrize("action", ["fiduciary_election.record", "request_item.send"])
def test_the_election_and_a_question_send_are_human_only(action: str) -> None:
    rule = _rules()[action]
    assert rule.get("agent") == "deny"
    assert "agent" not in _allowed(action) and "system" not in _allowed(action)


def test_no_client_role_records_the_election() -> None:
    rule = _rules()["fiduciary_election.record"]
    for role in ("client_admin", "client_contributor", "third_party", "system"):
        assert rule.get(role) == "deny"


@pytest.mark.parametrize(
    "role", ["engagement_partner", "manager", "senior", "staff", "client_admin", "agent"]
)
async def test_the_estate_header_offers_approve_values_only_where_the_matrix_allows(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    async def authorised(_ctx: object, _engagement: object, action: str) -> None:
        if role not in _allowed(action):
            raise Forbidden(action, "role")

    monkeypatch.setattr(estate_service, "_authorised", authorised)
    got = await estate_service.offered(cast(AuthContext, object()), uuid.uuid4())
    assert ("sign_off.l4" in got) == (role == "engagement_partner")
    if role in ("client_admin", "agent"):
        assert got == []
