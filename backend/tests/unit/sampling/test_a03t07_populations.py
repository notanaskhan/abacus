"""A-03-T07 (TASK-2611; A-03 §3 F2 US-2.1 to US-2.3; SPEC-580): populations and completeness ties,
by code, without a database.

The row's acceptance: "Census v2 yields 412 records and two ties, census v1 computes off
$182,300.00, Granite Peak's window yields 1,912 payments for $38,640,200, and an SSN column is
refused with 422 restricted_column."
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from abacus.modules.ledger.api import GlEntry
from abacus.modules.sampling.populations import (
    Built,
    ColumnMapInvalid,
    DuplicateRecordKey,
    GlQuery,
    PopulationUnreadable,
    RestrictedColumn,
    compute_tie,
    gl_records,
    gl_ties,
    parse_money,
    resolve_columns,
    upload_records,
)

HEADER = ["Participant ID", "Name", "Hire date", "Compensation", "SSN"]
MAP = {
    "record_key": "Participant ID",
    "name": "Name",
    "date": "Hire date",
    "amount": "Compensation",
}


def census(count: int, total: Decimal) -> list[list[str]]:
    """`count` rows whose compensation foots to `total`; an SSN column nobody maps."""
    each = (total / count).quantize(Decimal("1"))
    rows = [HEADER]
    for n in range(count):
        amount = each if n < count - 1 else total - each * (count - 1)
        rows.append(
            [f"NW-{2000 + n}", f"Participant {n}", "2020-01-06", f"{amount:,.2f}", "000-00-0000"]
        )
    return rows


def _codes(err: pytest.ExceptionInfo[Exception]) -> str:
    return str(getattr(err.value, "code", ""))


def test_ac1_census_v2_yields_412_records_and_its_total() -> None:
    built = upload_records(census(412, Decimal("14560000.00")), MAP)
    assert len(built.records) == 412
    assert built.total == Decimal("14560000.00")
    assert len(built.sha256) == 64
    first = built.records[0]
    assert set(built.display[first.key]) == {"name", "date"}  # display fields only


def test_ac1_the_canonical_hash_ignores_file_order() -> None:
    rows = census(412, Decimal("14560000.00"))
    reordered = [rows[0], *reversed(rows[1:])]
    assert upload_records(rows, MAP).sha256 == upload_records(reordered, MAP).sha256


def test_ac1_the_unmapped_ssn_column_is_never_copied() -> None:
    built = upload_records(census(3, Decimal("300.00")), MAP)
    for shown in built.display.values():
        assert "000-00-0000" not in shown.values()


@pytest.mark.parametrize(
    "column", ["SSN", "Social security number", "Date of birth", "Account number", "Routing no"]
)
def test_ac4_a_restricted_column_is_refused_422(column: str) -> None:
    rows = census(3, Decimal("300.00"))
    rows[0] = [*HEADER[:4], column]
    with pytest.raises(RestrictedColumn) as refused:
        upload_records(rows, {**MAP, "name": column})
    assert _codes(refused) == "restricted_column"
    assert refused.value.facts == {"field": "name"}


def test_ac4_ssn_values_under_an_innocent_header_are_refused_too() -> None:
    rows = [["Key", "Ref"], ["A1", "123-45-6789"], ["A2", "234-56-7890"]]
    with pytest.raises(RestrictedColumn):
        upload_records(rows, {"record_key": "Key", "name": "Ref"})


def test_ac1_formula_leading_cells_are_kept_as_text() -> None:
    rows = [["Key", "Name"], ["K1", '=HYPERLINK("http://x")'], ["K2", "+1"], ["K3", "@SUM(A1)"]]
    built = upload_records(rows, {"record_key": "Key", "name": "Name"})
    assert [built.display[k]["name"] for k in ("K1", "K2", "K3")] == [
        '=HYPERLINK("http://x")',
        "+1",
        "@SUM(A1)",
    ]


def test_ac1_columns_map_by_header_or_letter_and_bad_maps_are_refused() -> None:
    header = ["Participant ID", " Name ", "Comp"]
    assert resolve_columns(header, {"record_key": "A", "name": "name", "amount": "c"}) == {
        "record_key": 0,
        "name": 1,
        "amount": 2,
    }
    for bad in (
        {"name": "Name"},  # no record key
        {"record_key": "Participant ID", "salary": "Comp"},  # no such field
        {"record_key": "Participant ID", "name": "Department"},  # no such column
        {"record_key": "Participant ID", "name": "Z"},  # no such letter
        {"record_key": "A", "name": "Participant ID"},  # one column twice
    ):
        with pytest.raises(ColumnMapInvalid):
            resolve_columns(header, bad)


def test_ac1_amounts_parse_exactly_and_refuse_text() -> None:
    assert parse_money("$1,234.50") == Decimal("1234.50")
    assert parse_money("(12.00)") == Decimal("-12.00")
    assert parse_money("-7") == Decimal("-7")
    assert parse_money("  ") is None
    for bad in ("twelve", "NaN", "Infinity"):
        with pytest.raises(ColumnMapInvalid):
            parse_money(bad)


def test_ac1_duplicate_keys_blank_lines_and_empty_sheets() -> None:
    with pytest.raises(DuplicateRecordKey):
        upload_records([["Key"], ["NW-1"], ["nw-1 "]], {"record_key": "Key"})
    built = upload_records([[""], ["Key"], ["NW-1"], [""], ["NW-2"]], {"record_key": "Key"})
    assert [r.key for r in built.records] == ["NW-1", "NW-2"]
    with pytest.raises(PopulationUnreadable):
        upload_records([[""], [" "]], {"record_key": "Key"})
    with pytest.raises(PopulationUnreadable):
        upload_records([["Key"], [""]], {"record_key": "Key"})


# ---- US-2.2: ties --------------------------------------------------------------------------


def _cmp(label: str, amount: str) -> dict[str, object]:
    return {"label": label, "amount": amount, "citation_id": None, "ledger_ref": None}


def test_ac2_census_v2_ties_twice() -> None:
    total = upload_records(census(412, Decimal("14560000.00")), MAP).total
    paygrid = [_cmp("PayGrid YTD register", "14560000.00")]
    register = compute_tie("PayGrid YTD register", total, paygrid)
    w3 = compute_tie(
        "W-3 Box 1 + Box 12 D",
        total,
        [_cmp("W-3 Box 1", "13813400.00"), _cmp("W-3 Box 12 D", "746600.00")],
    )
    assert [(t.result, t.difference) for t in (register, w3)] == [
        ("tie", Decimal("0.00")),
        ("tie", Decimal("0.00")),
    ]


def test_ac2_census_v1_computes_off_182300() -> None:
    total = upload_records(census(409, Decimal("14377700.00")), MAP).total
    tie = compute_tie("PayGrid YTD register", total, [_cmp("PayGrid YTD register", "14560000.00")])
    assert tie.result == "off"
    assert tie.difference == Decimal("-182300.00")
    assert tie.difference is not None and abs(tie.difference) == Decimal("182300.00")


def test_ac2_no_total_or_no_comparison_is_check() -> None:
    assert compute_tie("Count", None, [_cmp("Register", "1.00")]).result == "check"
    assert compute_tie("Count", Decimal("1.00"), []).result == "check"


# ---- US-2.3: the general ledger ------------------------------------------------------------

QUERY = GlQuery(
    ("1010",), "credit", ("Payment", "Bill payment"), date(2026, 7, 1), date(2026, 9, 18)
)


def _line(n: int, **kw: object) -> GlEntry:
    values: dict[str, object] = {
        "line_no": n,
        "account_code": "1010",
        "account_name": "Front Range Bank operating",
        "posted_on": date(2026, 7, 1) + timedelta(days=n % 80),
        "reference": None,
        "kind": "Payment",
        "counterparty": "Vendor",
        "description": None,
        "debit": Decimal(0),
        "credit": Decimal(0),
        "source_ref": f"S{n}",
    }
    values.update(kw)
    return GlEntry(**values)  # type: ignore[arg-type] -- the fields as a test builds them


def granite_peak() -> list[GlEntry]:
    """1,912 credits on 1010 in the window totalling 38,640,200, and lines the query leaves out."""
    lines = [
        _line(
            n,
            credit=Decimal("20209") if n < 1912 else Decimal("38640200") - Decimal("20209") * 1911,
            kind="Payment" if n % 2 else "Bill payment",
        )
        for n in range(1, 1913)
    ]
    lines += [
        _line(5001, account_code="2000", credit=Decimal("10")),  # another account
        _line(5002, debit=Decimal("10")),  # the other side
        _line(5003, kind="Journal", credit=Decimal("10")),  # another kind
        _line(5004, posted_on=date(2026, 9, 19), credit=Decimal("10")),  # after the window
    ]
    return lines


def test_ac3_granite_peaks_window_yields_1912_payments_for_38640200() -> None:
    built = gl_records(granite_peak(), QUERY)
    assert len(built.records) == 1912
    assert built.total == Decimal("38640200")


def test_ac3_the_designed_ties_compute_by_code() -> None:
    lines = granite_peak()
    built = gl_records(lines, QUERY)
    first, second = gl_ties(lines, QUERY, built)
    # The Journal credit in the window is a credit to 1010 the kinds filter left out: off by 10.
    assert (first.result, first.difference) == ("off", Decimal("-10"))
    assert (second.result, second.explanation) == ("check", "Check numbers not in this export")
    clean = [e for e in lines if e.kind != "Journal"]
    assert gl_ties(clean, QUERY, gl_records(clean, QUERY))[0].result == "tie"


def test_ac3_check_numbers_with_and_without_gaps() -> None:
    def ties_for(refs: list[str]) -> tuple[str, str | None]:
        lines = [_line(n + 1, reference=r, credit=Decimal("100")) for n, r in enumerate(refs)]
        built = gl_records(lines, QUERY)
        tie = gl_ties(lines, QUERY, built)[1]
        return tie.result, tie.explanation

    assert ties_for(["1001", "1002", "1003", "ACH-7"]) == ("tie", None)
    assert ties_for(["1001", "1004"]) == ("check", "2 check numbers missing")


def test_ac3_an_empty_window_is_unreadable() -> None:
    with pytest.raises(PopulationUnreadable):
        gl_records([_line(1, account_code="2000", credit=Decimal("1"))], QUERY)


def test_built_is_frozen() -> None:
    built = upload_records([["Key"], ["A"]], {"record_key": "Key"})
    assert isinstance(built, Built)
    with pytest.raises(AttributeError):
        built.total = Decimal(1)  # type: ignore[misc] -- proving the dataclass is frozen
