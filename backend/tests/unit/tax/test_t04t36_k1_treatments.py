"""T-04-T36 (TASK-7309; SPEC-649 AC-7.2, AC-7.5; DEC-84, DEC-4309): the K-1 treatment rules, pure.

The database paths (Ridgeline's eight treatments, the 422, the release re-proposal) are
`tests/integration/agent_tests/test_t04t36_k1_treatments.py`."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax import k1_treatments as k1


def test_eight_kinds_each_name_their_line() -> None:
    assert len(k1.KINDS) == 8 and set(k1.LINE_OF_KIND) == set(k1.KINDS)
    assert k1.LINE_OF_KIND["tax_exempt_interest"] == "Box 18A"
    assert k1.LINE_OF_KIND["qbi_199a"] == "Box 20Z"


def test_only_a_treatment_that_differs_from_saly_reads_changed() -> None:
    assert k1.changed({"v": "Credit"}, {"v": "Deduction", "year": 2024})  # PTET (TXI-02 c)
    assert not k1.changed({"v": "Passive"}, {"v": "Passive", "year": 2024})
    assert not k1.changed({"v": "Passive"}, None)  # no SALY: unchanged


def test_an_override_reads_over_the_resolved_treatment() -> None:
    assert k1.treatment_text({"v": "Passive"}, {"t": "text", "v": "Nonpassive"}) == "Nonpassive"
    assert k1.treatment_text({"v": "Passive"}, None) == "Passive"
    assert k1.treatment_text(None, None) == "Default"


def test_a_release_that_moves_basis_makes_only_the_basis_treatment_stale() -> None:
    draft = {"1": Decimal("307900"), "L": Decimal("1912500"), "18A": Decimal("1550")}
    final = {"1": Decimal("307900"), "L": Decimal("1914050"), "18A": Decimal("1550")}
    moved = k1.moved_boxes(draft, final)
    assert moved == {"L"}
    approved = ["passive_nonpassive", "basis_at_risk", "tax_exempt_interest", "qbi_199a"]
    assert k1.stale_kinds(moved, approved) == ["basis_at_risk"]
    assert k1.stale_kinds(k1.moved_boxes(draft, draft), approved) == []
