"""A-05-T54 (TASK-6111; A-05 F9; EBP-07): the tie-out is code's.

Row acceptance: "Net assets tie at 16,812,400 = 14,228,500 + 2,583,900, the only differences are
15,060 and 33,540, and a draft 4a 'No' is flagged inconsistent." From A-05 §3 (Hannah's EBP-07),
not the implementation.
"""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.assurance import ebp_form5500 as service
from abacus.modules.assurance.compute.ebp import form5500 as engine


def test_net_assets_tie_as_a_sum() -> None:
    assert engine.sums_to(D("16812400"), [D("14228500"), D("2583900")])
    assert not engine.sums_to(D("16812400"), [D("14228500"), D("2583000")])


def test_the_receivable_is_the_only_difference_and_note_8_reconciles_it() -> None:
    lines = [("1a", D("14228500")), ("1b(2)", D("1221900")), ("1l", D("16812400"))]
    fs = {"1a": D("14228500"), "1b(2)": D("1270500"), "1l": D("16861000")}
    result = service.compute(lines, fs, [], D("0"))
    differences = {t.line_code: t.difference for t in result.lines if t.difference}
    assert differences == {"1b(2)": D("48600"), "1l": D("48600")}
    reconciled = engine.classify("1b(2)", D("1270500"), D("1221900"), [D("15060"), D("33540")])
    assert reconciled.classification == "reconciling_item"
    assert engine.classify("1a", D("14228500"), D("14228500")).classification == "tie"


def test_a_difference_without_its_basis_is_inconsistent() -> None:
    assert engine.classify("1b(2)", D("1270500"), D("1221900")).classification == "inconsistent"
    assert engine.classify("1b(2)", D("1270500"), D("1221900"), [D("15060")]).classification == (
        "inconsistent"
    )
    assert engine.classify("1c", None, D("1")).classification == "inconsistent"


def test_a_draft_4a_no_with_late_deposits_is_flagged() -> None:
    assert engine.part_iv_4a("no", None, D("33540")) == "inconsistent"
    assert engine.part_iv_4a("yes", D("33540"), D("33540")) == "consistent"
    assert engine.part_iv_4a("yes", D("30000"), D("33540")) == "inconsistent"
    assert engine.part_iv_4a("no", None, D("0")) == "consistent"
    result = service.compute([], {}, [("4a", "no", None)], D("33540"))
    assert result.counts.part_iv_inconsistent == 1


def test_captions_sum_into_their_schedule_h_line() -> None:
    by_line = engine.amounts_by_line(
        {
            "net_assets.receivable_employer": D("392100"),
            "net_assets.receivable_participant": D("878400"),
            "net_assets.unmapped": D("5"),
        },
        {
            "net_assets.receivable_employer": "1b(2)",
            "net_assets.receivable_participant": "1b(2)",
        },
    )
    assert by_line == {"1b(2)": D("1270500")}


def test_the_inputs_hash_moves_with_its_inputs() -> None:
    a = engine.classify("1a", D("1"), D("1"))
    b = engine.classify("1a", D("1"), D("2"))
    assert a.inputs_hash != b.inputs_hash and len(a.inputs_hash) == 64
