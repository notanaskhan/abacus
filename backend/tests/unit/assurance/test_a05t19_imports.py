"""A-05-T19 (TASK-3021; A-05 §4.10 F3; DEC-2068): tabular source imports, by code.

Row acceptance: "The Northwind census imports 301 participants with SSNs sealed, and a register
whose total does not foot is refused with the difference shown." The parse, footing and ties run
here on the synthetic Northwind files through evidence's extraction (cached values only); the
sealed write and the recorded refusal run against Postgres in
`tests/integration/backfill/test_a05t19_imports_db.py`.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.assurance.ebp_imports import (
    ImportMapInvalid,
    amount,
    census_ties,
    day,
    parse,
    ssn_digits,
)
from abacus.modules.evidence.extraction import CSV, XLSX, Table, extract
from abacus_tools.synthetic.scenarios.brightwater_hale import ebp

CENSUS_MAP = {
    "participant_key": "Participant",
    "name": "Name",
    "ssn": "SSN",
    "hire_on": "Hire date",
    "status": "Status",
    "compensation": "Compensation",
}
REGISTER_MAP = {"pay_date": "Pay date", "gross": "Gross wages", "deferral": "401(k) deferrals"}


def _table(content: bytes, media_type: str = XLSX) -> Table:
    extraction = extract(content, media_type)
    assert extraction.status == "extracted"
    return extraction.tables[0]


def test_ac_the_northwind_census_parses_301_participants_footing_to_14_560_000() -> None:
    parsed = parse("census", _table(ebp.census_xlsx()), CENSUS_MAP)
    assert parsed.refusal is None
    assert len(parsed.rows) == ebp.PARTICIPANTS_EOY == 301
    assert parsed.totals["compensation"] == D("14560000.00")
    first = parsed.rows[0]
    assert first["participant_key"] == "NW-1001"
    assert str(first["ssn"]).startswith("XXX-XX-")


def test_ac_the_census_ties_to_paygrid_and_the_w3() -> None:
    assert census_ties(D("14560000.00"), D("14560000.00"), ebp.W3_BOX1, ebp.W3_BOX12D) is None


def test_ac_a_census_that_does_not_tie_is_refused_with_each_difference() -> None:
    refusal = census_ties(D("14560000.00"), D("14559000.00"), ebp.W3_BOX1, D("746000.00"))
    assert refusal is not None and refusal.code == "import_not_tying"
    assert refusal.facts == {
        "differences": {"payroll_ytd": "1000.00", "w3_box1_plus_box12d": "600.00"}
    }


def test_ac_the_register_foots_to_its_keyed_control_total() -> None:
    wages = sum((p.wages for p in ebp.payrolls()), D(0))
    parsed = parse(
        "payroll_register",
        _table(ebp.payroll_register_xlsx()),
        REGISTER_MAP,
        {"gross": wages},
    )
    assert parsed.refusal is None
    assert len(parsed.rows) == ebp.PAYROLLS
    assert parsed.totals["gross"] == wages.quantize(D("0.01"))


def test_ac_a_register_that_does_not_foot_is_refused_with_the_difference() -> None:
    wages = sum((p.wages for p in ebp.payrolls()), D(0))
    parsed = parse(
        "payroll_register",
        _table(ebp.payroll_register_xlsx()),
        REGISTER_MAP,
        {"gross": wages + D("125.40")},
    )
    assert parsed.refusal is not None
    assert parsed.refusal.code == "import_not_footing"
    assert parsed.refusal.facts == {"differences": {"gross": "-125.40"}}


def test_ac_a_register_foots_to_its_own_total_row() -> None:
    content = (
        b"Pay date,Gross wages,401(k) deferrals\n2025-01-10,1000.00,60.00\n"
        b'2025-01-24,"1,000.50",60\nTotal,2000.50,120.00\n'
    )
    parsed = parse("payroll_register", _table(content, CSV), REGISTER_MAP)
    assert parsed.refusal is None
    assert parsed.totals == {"gross": D("2000.50"), "deferral": D("120.00")}


def test_ac_a_total_row_that_does_not_foot_shows_the_difference() -> None:
    content = (
        b"Pay date,Gross wages,401(k) deferrals\n2025-01-10,1000.00,60.00\nTotal,1000.01,60.00\n"
    )
    parsed = parse("payroll_register", _table(content, CSV), REGISTER_MAP)
    assert parsed.refusal is not None
    assert parsed.refusal.facts == {"differences": {"gross": "-0.01"}}


def test_a_register_with_no_total_at_all_is_refused() -> None:
    content = b"Pay date,Gross wages,401(k) deferrals\n2025-01-10,1000.00,60.00\n"
    parsed = parse("payroll_register", _table(content, CSV), REGISTER_MAP)
    assert parsed.refusal is not None and parsed.refusal.code == "import_no_control_total"


def test_a_bad_value_names_the_row_and_column_never_the_value() -> None:
    content = (
        b"Participant,Name,SSN,Hire date,Status,Compensation\n"
        b"NW-1,A,123-45-678,2020-01-01,active,100\n"
    )
    parsed = parse("census", _table(content, CSV), CENSUS_MAP)
    assert parsed.refusal is not None
    assert parsed.refusal.code == "import_bad_value"
    assert parsed.refusal.facts == {"row": 2, "column": "ssn"}
    assert "678" not in repr(parsed.refusal)


def test_a_duplicate_participant_is_refused() -> None:
    content = (
        b"Participant,Name,SSN,Hire date,Status,Compensation\n"
        b"NW-1,A,,2020-01-01,active,100\nNW-1,B,,2020-01-01,active,100\n"
    )
    parsed = parse("census", _table(content, CSV), CENSUS_MAP)
    assert parsed.refusal is not None and parsed.refusal.code == "import_duplicate_key"


@pytest.mark.parametrize(
    ("column_map", "facts"),
    [
        ({**CENSUS_MAP, "salary": "Compensation"}, {"unknown": "salary"}),
        (
            {k: v for k, v in CENSUS_MAP.items() if k != "name"},
            {"missing": "name"},
        ),
    ],
)
def test_a_map_that_names_no_such_field_or_misses_one_is_refused(
    column_map: dict[str, str], facts: dict[str, str]
) -> None:
    with pytest.raises(ImportMapInvalid) as refused:
        parse("census", _table(ebp.census_xlsx()), column_map)
    assert refused.value.facts == facts


def test_a_map_naming_a_header_the_file_lacks_is_refused() -> None:
    with pytest.raises(ImportMapInvalid) as refused:
        parse("census", _table(ebp.census_xlsx()), {**CENSUS_MAP, "dob": "Date of birth"})
    assert refused.value.facts == {"header_not_found": "dob"}


@pytest.mark.parametrize(
    ("raw", "value"),
    [("$1,234.50", D("1234.50")), ("(12.00)", D("-12.00")), ("-3", D("-3")), ("", None)],
)
def test_amounts_read_exactly(raw: str, value: D | None) -> None:
    assert amount(raw) == value


def test_dates_and_ssns_read_by_rule() -> None:
    assert str(day("3/9/1981")) == "1981-03-09"
    assert str(day("2025-01-15 00:00:00")) == "2025-01-15"
    assert ssn_digits("12345678") == "012345678"  # a numeric cell that lost its zero
    assert ssn_digits("XXX-XX-4417") == "XXX-XX-4417"
    with pytest.raises(ValueError, match="ssn"):
        ssn_digits("12-345-678")
