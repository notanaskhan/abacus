# ac-test-author: ayushkbhatia
"""A-04-T16 (TASK-2904; ADR-078): independent acceptance tests for A-04-T13's register, by code.

Written from A-04 §3.4 and the AUD-08 handoff, not from the builder's tests: the RMM golden over
every inherent and control risk pair of BH matrix v1 (typed here from the matrix's rule: Control
risk Max leaves the inherent risk), the tally against the handoff's grid, the register hash, and
the presumption rules the service enforces before any write.
"""

from __future__ import annotations

import uuid
from typing import Final

import pytest

from abacus.modules.assurance.risks import (
    RiskRow,
    area_key,
    register_hash,
    tally,
)
from abacus.modules.methodology.api import PolicyRef, RmmMatrixPayload
from abacus.modules.methodology.standards_contract import rmm_for

GOLDEN: Final = {
    ("low", "low"): "low",
    ("low", "moderate"): "low",
    ("low", "high"): "low",
    ("low", "max"): "low",
    ("moderate", "low"): "low",
    ("moderate", "moderate"): "moderate",
    ("moderate", "high"): "moderate",
    ("moderate", "max"): "moderate",
    ("high", "low"): "moderate",
    ("high", "moderate"): "high",
    ("high", "high"): "high",
    ("high", "max"): "high",
}
POLICY: Final = PolicyRef("bh-rmm-matrix", uuid.uuid4(), 1, "BH matrix v1")
MATRIX: Final = RmmMatrixPayload.model_validate(
    {
        "kind": "rmm_matrix",
        "rows": [
            {"inherent_risk": ir, "control_risk": cr, "rmm": rmm}
            for (ir, cr), rmm in GOLDEN.items()
        ],
    }
)
# The AUD-08 a grid: code, IR, RMM, significance, fraud, presumption, linked.
GRID: Final = (
    ("R1", "high", "high", "mandatory", "presumed", "management_override", True),
    ("R2", "moderate", "moderate", "none", "none", "none", True),
    ("R3", "high", "high", "proposed", "presumed", "revenue_recognition", True),
    ("R4", "low", "low", "none", "none", "none", True),
    ("R5", "low", "low", "none", "rebuttal_proposed", "revenue_recognition", True),
    ("R6", "moderate", "moderate", "none", "none", "none", True),
    ("R7", "moderate", "moderate", "none", "none", "none", True),
    ("R8", "high", "high", "none", "none", "none", False),
    ("R9", "low", "low", "none", "none", "none", True),
    ("R10", "moderate", "moderate", "none", "none", "none", True),
)


@pytest.mark.parametrize(("pair", "rmm"), sorted(GOLDEN.items()))
def test_rmm_golden_over_every_ir_cr_pair(pair: tuple[str, str], rmm: str) -> None:
    ir, cr = pair
    found = rmm_for(MATRIX, POLICY, inherent_risk=ir, control_risk=cr)  # type: ignore[arg-type] -- the grid's text ratings
    assert (found.rmm, found.policy) == (rmm, POLICY)


def test_a_pair_the_matrix_does_not_answer_is_never_guessed() -> None:
    partial = RmmMatrixPayload.model_validate(
        {
            "kind": "rmm_matrix",
            "rows": [{"inherent_risk": "low", "control_risk": "max", "rmm": "low"}],
        }
    )
    with pytest.raises(Exception) as refused:
        rmm_for(partial, POLICY, inherent_risk="high", control_risk="max")
    assert getattr(refused.value, "code", None) == "standard_row_missing"


def _rows() -> tuple[list[RiskRow], frozenset[uuid.UUID]]:
    rows: list[RiskRow] = []
    linked: set[uuid.UUID] = set()
    for code, ir, rmm, significance, fraud, presumption, is_linked in GRID:
        row = RiskRow(
            id=uuid.uuid4(),
            code=code,
            inherent_risk=ir,
            control_risk="max",
            rmm=rmm,
            significance=significance,
            fraud=fraud,
            presumption_kind=presumption,
            status="draft",
            content_hash=f"{int(code[1:]):064x}",
        )
        rows.append(row)
        if is_linked:
            linked.add(row.id)
    return rows, frozenset(linked)


def test_the_tally_equals_the_grid() -> None:
    rows, linked = _rows()
    found = tally(rows, linked)
    assert (found.risks, found.significant, found.significant_proposed) == (10, 2, 1)
    assert (found.fraud, found.high_rmm, found.unaddressed) == (2, 3, 1)
    assert found.ep_approval == "pending"


def test_ep_approval_reads_approved_only_when_every_row_is_and_changed_after_a_revision() -> None:
    rows, linked = _rows()
    for r in rows:
        r.status = "ep_approved"
    assert tally(rows, linked).ep_approval == "approved"
    rows[3].status = "revised"
    assert tally(rows, linked).ep_approval == "changed"


def test_the_register_hash_moves_with_any_row_and_ignores_order() -> None:
    rows, _ = _rows()
    first = register_hash(rows)
    assert register_hash(list(reversed(rows))) == first
    rows[7].content_hash = "f" * 64
    assert register_hash(rows) != first


def test_area_keys_are_stable_slugs() -> None:
    assert area_key("Contributions — remittance & cutoff") == "contributions_remittance_cutoff"
    assert area_key("Disclosures — parties in interest") == "disclosures_parties_in_interest"
