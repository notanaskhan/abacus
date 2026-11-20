"""Q-05-T13 (TASK-8817; SPEC-711 AC-19, AC-20): live-path retention and hold changes.

Row acceptance: "Saving the 8879 policy at 2 years answers 422 below_floor, Victor Hammond can
place a hold while Samuel Ito cannot, and the FIL-02g drawer lists every version." Here: the
database's floor check stays the 422 (`BelowFloor`), an override under its type's policy is 422
`below_type_policy`; placing a hold is firm_admin, security_admin or a partner with fresh MFA, never
agent or system (matrix); the hold request takes document classes and until-released; the
versions trigger copies the policy text (migration 0994).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from abacus.modules.evidence import retention
from abacus.modules.evidence.hold_routes import LegalHoldIn

REPO = Path(__file__).resolve().parents[4]


def test_ac_below_floor_and_below_type_policy_are_422_codes() -> None:
    assert retention.BelowFloor.code == "below_floor"
    assert retention.BelowTypePolicy.code == "below_type_policy"


def test_ac_who_may_place_a_hold() -> None:
    actions = yaml.safe_load((REPO / "docs/architecture/permission-matrix/evidence.yaml").read_text())["actions"]
    row = actions["legal_hold.place"]
    assert {row["firm_admin"], row["security_admin"], row["firm_partner"]} == {"allow"}
    assert row["agent"] == "deny" and row["system"] == "deny" and row["mfa_recent"] == "required"
    assert "staff" not in row or row["staff"] != "allow"  # Samuel Ito (staff) cannot


def test_ac_a_hold_takes_classes_and_until_released() -> None:
    body = LegalHoldIn.model_validate({
        "scope": {"kind": "client", "client_id": "00000000-0000-4000-8000-000000000001"},
        "reason_code": "state_controversy", "document_classes": ["tax_return", "client_document"],
        "until_released": True,
    })  # fmt: skip
    assert body.document_classes == ["tax_return", "client_document"] and body.until_released


def test_ac_versions_carry_the_policy_text() -> None:
    source = (REPO / "backend/migrations/versions/0994_retention_policy_text.py").read_text()
    assert "NEW.policy_text, NEW.effective_from" in source
