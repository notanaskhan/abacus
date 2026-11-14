"""T-07-T08 (TASK-8022; T-07 §5.3; SPEC-656 AC-15.6; DEC-5011): every TXT figure foots in a seed
test. Row acceptance: "Every TXT figure foots in a seed test (430,000; 400,000; 240,000; 60,000 /
180,000 / 144,000; 16,400,000; 15,993,000; 12,688,000; 900,000)." Arithmetic here is the test's
check of the seed's own figures, never the product computing them (ADR-050: T-07-T09's engine
reproduces them)."""

from __future__ import annotations

from decimal import Decimal

from abacus_tools.synthetic.scenarios.brightwater_hale import fiduciary_slice as s

D = Decimal


def test_calloway_fai_less_fees_is_dni_and_the_fees_split_by_character() -> None:
    lines = {line.kind: line.amount for line in s.FAI_LINES}
    fai = lines["interest"] + lines["ordinary_dividends"]
    assert fai == s.CALLOWAY["fai"] == D("430000.00")
    # Fees charged to principal, allocated pro rata by character: 25% interest, 75% dividends.
    assert s.CALLOWAY["fees_to_interest"] + s.CALLOWAY["fees_to_dividends"] == s.TRUSTEE_FEES
    assert lines["interest"] - s.CALLOWAY["fees_to_interest"] == s.CALLOWAY["dni_interest"]
    dividends = lines["ordinary_dividends"] - s.CALLOWAY["fees_to_dividends"]
    assert dividends == s.CALLOWAY["dni_dividends"]
    assert fai - s.TRUSTEE_FEES == s.CALLOWAY["dni"] == D("400000.00")
    assert lines["qualified_dividends"] <= lines["ordinary_dividends"]


def test_calloway_idd_is_the_lesser_of_distributions_and_dni() -> None:
    paid = sum((d.amount for d in s.DISTRIBUTIONS), D(0))
    assert min(paid, s.CALLOWAY["dni"]) == s.CALLOWAY["idd"] == D("240000.00")
    assert s.CALLOWAY["dni"] - s.CALLOWAY["idd"] == s.CALLOWAY["retained_dni"]
    assert s.CALLOWAY["retained_dni"] - s.CALLOWAY["exemption"] == s.CALLOWAY["taxable_income"]
    assert s.CALLOWAY["fai"] - s.CALLOWAY["idd"] == s.CALLOWAY["fai_not_distributed"]


def test_calloway_k1_boxes_tie_to_the_deduction() -> None:
    totals = [sum((row[i] for row in s.ALLOCATIONS), D(0)) for i in (1, 2, 3, 4)]
    assert totals == [D("240000.00"), D("60000.00"), D("180000.00"), D("144000.00")]
    assert totals[0] == s.CALLOWAY["idd"]
    for _, dni, box_1, box_2a, box_2b in s.ALLOCATIONS:
        assert box_1 + box_2a == dni
        assert box_2b <= box_2a


def test_calloway_changed_and_scenario_states_foot() -> None:
    nora = sum((d.amount for d in s.DISTRIBUTIONS if d.beneficiary == "Nora Calloway"), D(0))
    assert nora + s.CHANGED_THEO_DEC_15 == s.CHANGED["distributions"] == s.CHANGED["idd"]
    theo_dni, box_1, box_2a, box_2b = s.CHANGED_THEO
    assert box_1 + box_2a == theo_dni and box_2b <= box_2a
    assert s.CALLOWAY["dni"] - s.CHANGED["idd"] == s.CHANGED["retained_dni"]
    assert s.CHANGED["retained_dni"] - s.CALLOWAY["exemption"] == s.CHANGED["taxable_income"]
    assert s.SCENARIO["nora"] + s.SCENARIO["theo"] == s.SCENARIO["distributions"]
    assert s.CALLOWAY["dni"] - s.SCENARIO["distributions"] == s.SCENARIO["retained"]


def test_calloway_clause_governed_determinations_each_name_a_clause() -> None:
    governed = {"grantor_status", "trust_type", "fai_definition", "trustee_fees"}
    governed |= {"principal_invaded"}
    for key, (_, clause) in s.DETERMINATIONS.items():
        assert (clause is not None) == (key in governed), key
        assert clause is None or clause in s.CLAUSES
    assert len({c for _, c in s.DETERMINATIONS.values() if c}) == 5


def test_thornbury_inventory_foots() -> None:
    assert sum((a.dod_value for a in s.ESTATE_ASSETS), D(0)) == D("16400000.00")
    assert sum((a.avd_value for a in s.ESTATE_ASSETS), D(0)) == D("15993000.00")
    basis = sum((a.basis_to_1041 for a in s.ESTATE_ASSETS if a.basis_to_1041), D(0))
    assert basis == s.THORNBURY["basis_to_1041"] == D("12688000.00")
    assert {a.schedule for a in s.ESTATE_ASSETS if a.basis_to_1041 is None} == {"D", "I"}
    assert {a.schedule for a in s.ESTATE_ASSETS if a.status == "gathering_support"} == {"D", "F"}


def test_thornbury_deductions_and_computation_foot() -> None:
    deductions = sum((amount for _, amount, _ in s.ESTATE_DEDUCTIONS), D(0))
    assert deductions == s.THORNBURY["deductions"] == D("900000.00")
    taxable = s.THORNBURY["gross_estate"] - deductions
    assert taxable == s.THORNBURY["taxable_estate"] == D("15500000.00")
    gifts = sum((gift - exclusion for _, _, _, gift, exclusion, _ in s.GIFTS), D(0))
    assert gifts == s.THORNBURY["adjusted_taxable_gifts"] == D("1200000.00")
    assert taxable + gifts == s.THORNBURY["tentative_base"]
    # §2001(c): 345,800 + 40% of the excess over 1,000,000.
    tentative = D("345800.00") + (s.THORNBURY["tentative_base"] - D("1000000.00")) * D("0.40")
    assert tentative == s.THORNBURY["tentative_tax"] == D("6625800.00")
    assert s.THORNBURY["bea"] + s.DSUE == s.THORNBURY["applicable_exclusion"]
    assert s.THORNBURY["gross_estate"] + gifts == s.THORNBURY["filing_threshold_test"]
    assert s.THORNBURY["filing_threshold_test"] > s.THORNBURY["bea"]
    without = s.THORNBURY["tentative_tax"] - s.THORNBURY["without_dsue_credit"]
    assert without == s.THORNBURY["without_dsue_tax"] == D("680000.00")


def test_the_snapshots_and_due_dates_are_the_epics() -> None:
    assert s.SNAPSHOTS["e0"].isoformat().startswith("2026-09-14T09:24")
    assert s.DUE[0].isoformat() == "2026-11-02" and s.DUE[1].isoformat() == "2027-05-03"
