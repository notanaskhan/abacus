"""T-04-T39 (TASK-7410; T-04 §3.8 AC-8.1 to AC-8.6; DEC-4409): residency and state allocation,
pure parts, on the Feld 2025 figures: 281 NYC days with a co-op abode → full-year NYS and NYC
with no conflict; 150 days with Rhinebeck as the main home → a conflict; allocation 268,400 +
6,910 + 14,820 + 307,900 = 598,030; NY AGI 615,605 = 598,030 + 1,550 + 16,025 (IT-225 4,746 +
11,279); IT-112-R min(11,279, 41,070 x 238,623 / 615,605 = 15,920) = 11,279."""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from openpyxl import load_workbook

from abacus.modules.tax.compute.individual.residency import residency_rules
from abacus.modules.tax.residency_service import (
    ALLOCATION_FIELDS,
    OPTIONS,
    Source,
    allocate_from,
    allocation_xlsx,
    client_question,
    facts_from_sources,
    residency_inputs,
    status_of,
)

D = Decimal
C = [uuid.uuid4() for _ in range(6)]
FELD = {
    "wages": D(268_400),
    "interest": D(6_910),
    "dividends": D(14_820),
    "rental_k1": D(307_900),
    "ny_addition_l20": D(1_550),
    "it225_ptet": D(4_746),
    "it225_other_state": D(11_279),
    "other_state_tax": D(11_279),
    "ny_tax": D(41_070),
    "other_state_income": D(238_623),
}


def _sources(days: int, main_home: str) -> list[Source]:
    return [
        Source("organizer", C[0], {"nyc_days": days, "main_home": main_home}),
        Source("coop_statement", C[1], {"place": "New York City"}),
        Source("deed", C[2], {"place": "Rhinebeck"}),
        Source("w2_box20", C[3], {"locality": "NYC"}),
        Source("w2_box20", C[4], {"locality": "NYC"}),
        Source("1099_address", C[5], {"place": "New York, NY"}),
    ]


def test_every_fact_is_stated_by_code_with_its_citations() -> None:
    facts = facts_from_sources(_sources(281, "New York City"))
    by = {(f.key, f.value.get("t")): f for f in facts}
    assert by[("days", "days")].value["nyc"] == 281
    assert by[("days", "days")].citation_ids == (C[0],)
    assert by[("domicile", "nyc_abode")].citation_ids == (C[1],)
    assert by[("second_residence", "second_residence")].value["places"] == ["Rhinebeck"]
    assert by[("work_location", "localities")].citation_ids == (C[3], C[4])
    assert by[("trigger", "addresses")].source_kind == "document"
    assert all(f.citation_ids for f in facts)


def test_281_days_with_an_abode_is_full_year_without_conflict() -> None:
    call = residency_rules(
        residency_inputs(facts_from_sources(_sources(281, "New York City"))), 2025
    )
    assert (call.recommended, call.conflict) == ("full_year_nys_nyc", False)


def test_150_days_with_rhinebeck_as_main_home_conflicts() -> None:
    inputs = residency_inputs(facts_from_sources(_sources(150, "Rhinebeck")))
    assert inputs.nyc_days == 150 and inputs.main_home_outside_nyc and inputs.has_nyc_abode
    call = residency_rules(inputs, 2025)
    assert (call.recommended, call.conflict) == ("full_year_nys_part_year_nyc", True)


def test_the_options_and_the_forms_they_add() -> None:
    assert [(o.key, o.adds_forms) for o in OPTIONS] == [
        ("full_year_nys_nyc", ()),
        ("full_year_nys_part_year_nyc", ("it360_1",)),
        ("part_year_nys", ("it203",)),
    ]


def test_the_status_words() -> None:
    assert status_of(False, False) == "review_point"
    assert status_of(False, True) == "action_required"
    assert status_of(True, True) == "confirmed"


def test_the_client_question_is_template_words_with_the_recommendation_first() -> None:
    title, wording = client_question("full_year_nys_part_year_nyc")
    assert title.startswith("Confirm your New York residency")
    lines = [ln for ln in wording.splitlines() if ln.startswith("- ")]
    assert lines[0] == "- Full-year New York State, part-year New York City"
    assert len(lines) == 3
    assert not any(ch.isdigit() for ch in wording)  # no figure, no day count, no note


def test_the_feld_allocation_foots() -> None:
    view = allocate_from(FELD)
    assert view.federal_total == D(598_030)
    assert view.addbacks == D(16_025)
    assert view.ny_agi == D(615_605)
    assert (view.credit, view.credit_limit) == (D(11_279), D(15_920))
    assert view.missing == ()


def test_a_missing_input_is_named_and_its_dependants_read_none() -> None:
    partial = {k: v for k, v in FELD.items() if k != "it225_ptet"}
    view = allocate_from(partial)
    assert view.missing == ("it225_ptet",)
    assert view.federal_total == D(598_030)
    assert view.addbacks is None and view.ny_agi is None and view.credit is None
    assert set(ALLOCATION_FIELDS) == set(FELD)


def test_the_xlsx_is_deterministic_and_carries_numbers_not_dollar_strings() -> None:
    first = allocation_xlsx(allocate_from(FELD))
    assert first == allocation_xlsx(allocate_from(FELD))
    sheet = load_workbook(io.BytesIO(first), read_only=True)["State allocation"]
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("Jurisdiction", "Line", "Amount", "Derivation")
    amounts = [r[2] for r in rows[1:]]
    assert 598030 in amounts and 615605 in amounts
    assert not any(isinstance(a, str) and "$" in a for a in amounts)
