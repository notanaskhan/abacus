"""F-03-T12: the platform's gates per type family; a firm can only add (DEC-39)."""

from __future__ import annotations

from abacus.modules.engagements.gate_policy import FAMILY, required_gates
from abacus.modules.engagements.service import EngagementType


def test_t12_every_type_has_a_family_and_no_excluded_type_exists() -> None:
    types = set(EngagementType.__args__)
    assert set(FAMILY) == types and len(types) == 14
    assert not types & {"audit", "single_audit", "yellow_book"}


def test_t12_platform_gates_per_family() -> None:
    assert required_gates("ebp_audit") == [f"G{n}" for n in range(1, 10)]
    assert required_gates("compilation") == ["G1", "G3", "G5", "G8", "G9"]
    assert required_gates("cas_monthly_close") == ["G1", "G3"]
    assert required_gates("notice_response") == ["G3"]


def test_t12_a_firm_override_adds_a_gate_and_cannot_remove_one() -> None:
    assert required_gates("cas_monthly_close", [("G2", "required")]) == ["G1", "G2", "G3"]
    assert "G1" in required_gates("tax_compliance", [("G7", "strict")])
