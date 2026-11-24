"""T-08-T23 (TASK-8916; T-08 AC4.2; TAX-14; ADR-050; OQ-3; DEC-5918; amber): the 1065 v4 check
library, one golden case set per bound check.

Row acceptance: "Ridgeline fails C-17 off 6,200 and C-31 with anchors that match its open issues,
and every bound check is a pure function with a golden test." Here: Ridgeline's facts (Schedule L
total assets 17,914,500, liabilities 11,054,500, so line 21 is 6,860,000; M-2 line 9 6,853,800
before the tax-exempt interest; the Pell Street II transfer with the §754 decision still out)
fail exactly C-17 (off 6,200, linking the open `tie_out:item_l_m2` issue) and C-31 (linking
`decision:section_754`) among the eight; every registered check code has golden pass, exception
and not-applicable cases here, run on the pure function with no I/O.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax import standards_checks as sc
from abacus.modules.tax.standards_checks import Facts

D = Decimal


def _cells(**cells: object) -> dict[str, dict[str, object] | None]:
    return {k.replace("_", "!", 1): {"v": v} for k, v in cells.items()}


def _ridgeline_values() -> dict[str, dict[str, object] | None]:
    lines = [("L1", "1240500"), ("L9a", "18900000"), ("L9b", "-2950000"), ("L11", "724000"),
             ("L15", "-215000"), ("L19b", "-10839500"), ("M-3 perm.", "6200")]  # fmt: skip
    values: dict[str, dict[str, object] | None] = {}
    for n, (key, net) in enumerate(lines, start=2):
        values[f"03!A{n}"], values[f"03!C{n}"] = {"v": key}, {"v": net}
    # 01: the trial balance foots (its total row F is zero).
    values |= _cells(**{"01_A2": "1000", "01_F2": "100", "01_A3": "2000", "01_F3": "-100",
                        "01_F4": "0"})  # fmt: skip
    # 05/07: two partners' capital rolls forward to 6,853,800 = M-2 line 9 (the omission's gap).
    values |= _cells(**{"05_A2": "Calder Holdings LLC", "05_B2": "6000000", "05_C2": "0",
                        "05_D2": "200000", "05_E2": "900000", "05_F2": "6700000",
                        "05_A3": "Mara Ostrowski", "05_B3": "150000", "05_C3": "0",
                        "05_D3": "0", "05_E3": "3800", "05_F3": "153800",
                        "07_B1": "6150000", "07_B9": "6853800"})  # fmt: skip
    # 04 and 08: the allocation and the state apportionment rows.
    values |= _cells(**{"04_A2": "Calder Holdings LLC", "08_A2": "IL"})
    # 06/09: Schedule K line 2 and the two K-1 columns that sum to it.
    values |= _cells(**{"06_A2": "2", "06_B2": "Net rental real estate income",
                        "06_C2": "1231600", "09_B1": "Calder Holdings LLC", "09_B2": "1206968",
                        "09_C1": "Mara Ostrowski", "09_C2": "24632"})  # fmt: skip
    return values


RIDGELINE = Facts(
    form="1065", values=_ridgeline_values(), partners=2, partners_missing_tin=0,
    k1_recipients=2, engine_lines={"1065.item_i": D(2)}, has_engine_summary=True,
    profile={"principal_activity": "Real estate rental", "business_code": "531110",
             "accounting_method": "accrual", "books_basis": "tax",
             "partnership_representative_contact_id": "pr", "prior_year_return_id": "py"},
    unmapped=0, transfers=1, section_754="sent_to_client", states=("CO", "IL", "NY"),
    ptet_elections={"CO": "not_elected", "IL": "elected", "NY": "not_elected"},
    ptet_paid={"IL": D("41000")}, ownership_periods=3, assets_registered=12,
    original_due_on=date(2026, 3, 16),
)  # fmt: skip


def test_ridgeline_fails_c17_off_6200_and_c31_and_passes_the_other_six() -> None:
    outcomes = {code: check(RIDGELINE) for code, (_label, check) in sc.NAMED.items()}
    failed = sorted(code for code, r in outcomes.items() if r.outcome == "exception")
    assert failed == ["check.m2_line9_schedule_l21", "check.section_754_documented"]
    c17 = outcomes["check.m2_line9_schedule_l21"]
    assert c17.difference == D("-6200") and c17.issue_ref == "tie_out:item_l_m2"
    assert c17.anchor == {"sheet": "07", "range": "B9"}
    assert c17.title == "Schedule M-2 line 9 equals Schedule L line 21: off 6,200"
    c31 = outcomes["check.section_754_documented"]
    assert c31.issue_ref == "decision:section_754" and c31.anchor == {"tab": "basis"}
    assert all(r.outcome == "pass" for c, r in outcomes.items() if c not in failed), {
        c: r.outcome for c, r in outcomes.items()
    }


def test_total_assets_and_line_21_by_code() -> None:
    from abacus.modules.tax.form_preview_blockers import schedule_l_line_21

    assert sc.total_assets(RIDGELINE.values) == D("17914500")
    assert schedule_l_line_21(RIDGELINE.values) == D("6860000")  # type: ignore[arg-type]


# --- the golden cases: (facts, outcome, reference) per named check -------------------------------

NONE = Facts(form="1065")
GOLDEN: dict[str, list[tuple[Facts, str, str | None]]] = {
    "check.k1_count_item_i": [
        (RIDGELINE, "pass", None),
        (replace(RIDGELINE, engine_lines={"1065.item_i": D(3)}), "exception", "check:k1_count"),
        (replace(RIDGELINE, engine_lines={}), "pass", None),  # 09's two columns
        (NONE, "not_applicable", None),
    ],
    "check.schedule_k_k1_sum": [
        (RIDGELINE, "pass", None),
        (
            replace(RIDGELINE, values={**RIDGELINE.values, "09!C2": {"v": "24000"}}),
            "exception",
            "tie_out:k1_sum_k",
        ),
        (NONE, "not_applicable", None),
    ],
    "check.m3_required": [
        (RIDGELINE, "pass", None),  # 17,914,500 of assets with M-3 lines mapped
        (
            replace(
                RIDGELINE,
                values={
                    k: v for k, v in RIDGELINE.values.items() if not (k == "03!A8" or k == "03!C8")
                },
            ),
            "exception",
            "check:m3_required",
        ),
        (NONE, "not_applicable", None),
    ],
    "check.tb_balanced_mapped": [
        (RIDGELINE, "pass", None),
        (replace(RIDGELINE, unmapped=3), "exception", "check:tb_unmapped"),
        (
            replace(RIDGELINE, values={**RIDGELINE.values, "01!F4": {"v": "250"}}),
            "exception",
            "tie_out:tb_foots",
        ),
        (NONE, "not_applicable", None),
    ],
    "check.m2_line9_schedule_l21": [
        (replace(RIDGELINE, values={**RIDGELINE.values, "07!B9": {"v": "6860000"}}), "pass", None),
        (RIDGELINE, "exception", "tie_out:item_l_m2"),
        (NONE, "not_applicable", None),
    ],
    "check.partnership_representative": [
        (RIDGELINE, "pass", None),
        (replace(RIDGELINE, profile={}), "exception", "check:partnership_representative"),
    ],
    "check.section_754_documented": [
        (replace(RIDGELINE, section_754="decided"), "pass", None),
        (RIDGELINE, "exception", "decision:section_754"),
        (replace(RIDGELINE, transfers=0), "not_applicable", None),
    ],
    "check.ptet_recorded": [
        (RIDGELINE, "pass", None),
        (replace(RIDGELINE, ptet_paid={}), "exception", "check:ptet_recorded"),
        (
            replace(RIDGELINE, ptet_elections={"IL": "elected"}, ptet_paid={"IL": D(1)}),
            "exception",
            "check:ptet_recorded",
        ),
        (replace(RIDGELINE, states=()), "not_applicable", None),
    ],
}


@pytest.mark.parametrize(
    ("code", "case"),
    [(code, i) for code, cases in GOLDEN.items() for i in range(len(cases))],
)
def test_named_check_golden(code: str, case: int) -> None:
    facts, outcome, ref = GOLDEN[code][case]
    found = sc.NAMED[code][1](facts)
    assert (found.outcome, found.issue_ref) == (outcome, ref)


def test_every_presence_check_has_pass_missing_and_its_reference() -> None:
    bare = replace(
        NONE, partners=2, partners_missing_tin=2, states=("IL",), profile={},
        has_engine_summary=False,
    )  # fmt: skip
    for code, label, predicate, anchor in sc.PRESENCE:
        check = sc.presence_check(code, predicate, anchor, label)
        assert check(RIDGELINE).outcome == "pass", code
        missing = check(bare)
        if missing.outcome == "pass":  # `partners` needs none at all
            missing = check(replace(bare, partners=0))
        if missing.outcome == "not_applicable":
            continue
        what = code.removeprefix("presence.")
        assert (missing.outcome, missing.issue_ref, missing.anchor) == (
            "exception", f"presence:{what}", anchor,
        ), code  # fmt: skip
    code, label, predicate, anchor = next(p for p in sc.PRESENCE if p[0] == "presence.state_sheet")
    na = sc.presence_check(code, predicate, anchor, label)
    assert na(replace(RIDGELINE, states=())).outcome == "not_applicable"


def test_every_bound_check_is_pure_and_golden_covered() -> None:
    assert set(GOLDEN) == set(sc.NAMED)
    for _label, check in sc.NAMED.values():
        source = inspect.getsource(check)
        assert "await" not in source and "session" not in source  # no I/O in a check
    import abacus.api as composition_root

    assert composition_root
    from abacus.modules.tax import standards_runs

    registered = set(standards_runs._CHECKS)  # pyright: ignore[reportPrivateUsage]
    assert set(sc.NAMED) | {c for c, *_ in sc.PRESENCE} <= registered
