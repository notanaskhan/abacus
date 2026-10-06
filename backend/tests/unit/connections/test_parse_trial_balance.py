"""AC-9, AC-11: `connections.api.parse_trial_balance`, the hardened provider parser (TASK-010a
contract revision 1, "Parsing"; ADR-038, ADR-050, AGENTS.md rule 8).

Expectations come from the contract: every `payload_too_large`, `malformed_payload` and
`invalid_amount` clause. The validate checks are in `tests/unit/ledger/test_validate.py`.
"""

from __future__ import annotations

import copy
import json
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from abacus.modules.connections.api import parse_trial_balance
from abacus.modules.ledger.api import LedgerLine, NormaliseError, validate
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import trial_balance_document

START = date(2025, 1, 1)
END = date(2025, 12, 31)
Doc = dict[str, object]


def _document() -> Doc:
    return {
        "provider": "fake",
        "currency": "USD",
        "dataset": "trial_balance",
        "period": {"start": "2025-01-01", "end": "2025-12-31"},
        "lines": [
            {
                "id": "acct-1000",
                "code": "1000",
                "name": "Cash",
                "debit": "150.00",
                "credit": "0.00",
            },
            {
                "id": "acct-4000",
                "code": "4000",
                "name": "Sales",
                "debit": "0.00",
                "credit": "150.00",
            },
        ],
        "control_totals": {"debit": "150.00", "credit": "150.00"},
    }


def _bytes(document: object) -> bytes:
    return json.dumps(document).encode()


def _lines(document: Doc) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], document["lines"])


def _with(**changes: object) -> bytes:
    document = _document()
    document.update(changes)
    return _bytes(document)


def _with_line(index: int, **changes: object) -> bytes:
    document = _document()
    _lines(document)[index].update(changes)
    return _bytes(document)


def _without_line_field(field: str) -> bytes:
    document = _document()
    del _lines(document)[0][field]
    return _bytes(document)


def _with_totals(**changes: object) -> bytes:
    document = _document()
    cast(dict[str, object], document["control_totals"]).update(changes)
    return _bytes(document)


def _code(content: bytes) -> str:
    with pytest.raises(NormaliseError) as raised:
        parse_trial_balance(content)
    return raised.value.code


# --- the happy path --------------------------------------------------------------------------


def test_ac9_a_provider_document_parses_to_the_common_model() -> None:
    tb = parse_trial_balance(_bytes(_document()))
    assert (tb.period_start, tb.period_end) == (START, END)
    assert [
        (line.account_code, line.account_name, line.debit, line.credit, line.source_ref)
        for line in tb.lines
    ] == [
        ("1000", "Cash", Decimal("150.00"), Decimal("0.00"), "acct-1000"),
        ("4000", "Sales", Decimal("0.00"), Decimal("150.00"), "acct-4000"),
    ]
    assert (tb.declared_debit, tb.declared_credit) == (Decimal("150.00"), Decimal("150.00"))
    assert all(isinstance(line, LedgerLine) for line in tb.lines)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("100", "100.00"), ("1.5", "1.50"), ("0", "0.00"), ("12.34", "12.34"), ("0.01", "0.01")],
)
def test_ac9_amounts_are_decimals_quantised_to_cents(text: str, expected: str) -> None:
    tb = parse_trial_balance(_with_line(0, debit=text))
    assert isinstance(tb.lines[0].debit, Decimal)
    assert str(tb.lines[0].debit) == expected


def test_ac9_the_largest_amount_below_the_limit_is_accepted() -> None:
    tb = parse_trial_balance(_with_line(0, debit="999999999999999.99"))
    assert tb.lines[0].debit == Decimal("999999999999999.99")


def test_ac9_declared_totals_are_decimals_quantised_to_cents() -> None:
    tb = parse_trial_balance(_with_totals(debit="150", credit="150.5"))
    assert (str(tb.declared_debit), str(tb.declared_credit)) == ("150.00", "150.50")


def test_ac9_line_order_is_preserved() -> None:
    document = _document()
    _lines(document).reverse()
    tb = parse_trial_balance(_bytes(document))
    assert [line.account_code for line in tb.lines] == ["4000", "1000"]


def test_ac9_a_document_with_no_lines_parses_and_validate_calls_it_empty() -> None:
    document = _document()
    document["lines"] = []
    tb = parse_trial_balance(_bytes(document))
    assert tb.lines == ()
    assert validate(tb, period_start=START, period_end=END) == "empty"


def test_ac9_exactly_50000_lines_are_accepted() -> None:
    document = _document()
    document["lines"] = [
        {"id": f"a{n}", "code": str(n), "name": "n", "debit": "0.00", "credit": "0.00"}
        for n in range(50_000)
    ]
    assert len(parse_trial_balance(_bytes(document)).lines) == 50_000


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ac9_a_synthetic_trial_balance_parses_and_validates(seed: int) -> None:
    entity = generate(seed).client_entities[0]
    tb = entity.trial_balances[-1]
    document = trial_balance_document(
        tb, period_start=entity.period_start, entity_name=entity.name
    )
    normalised = parse_trial_balance(_bytes(document))
    assert validate(normalised, period_start=entity.period_start, period_end=tb.as_of) is None
    assert len(normalised.lines) == len(tb.lines)
    assert sum((line.debit for line in normalised.lines), Decimal(0)) == tb.total_debits


def test_ac9_decimal_arithmetic_is_exact() -> None:
    document = _document()
    document["lines"] = [
        {"id": "a", "code": "1", "name": "A", "debit": "0.10", "credit": "0.00"},
        {"id": "b", "code": "2", "name": "B", "debit": "0.20", "credit": "0.00"},
        {"id": "c", "code": "3", "name": "C", "debit": "0.00", "credit": "0.30"},
    ]
    document["control_totals"] = {"debit": "0.30", "credit": "0.30"}
    assert (
        validate(parse_trial_balance(_bytes(document)), period_start=START, period_end=END) is None
    )


# --- malformed_payload -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not json",
        b"{",
        b'{"dataset": "trial_balance"',
        b"\xff\xfe\x00{}",
        b"\xc3\x28",
        b"NaN",
    ],
    ids=["empty", "text", "unclosed", "truncated", "bad-utf8-bom", "bad-utf8", "nan"],
)
def test_ac9_invalid_json_or_utf8_is_malformed(content: bytes) -> None:
    assert _code(content) == "malformed_payload"


@pytest.mark.parametrize(
    "document",
    [[], [_document()], "text", 7, 1.5, None, True],
    ids=["array", "array-of-document", "string", "int", "float", "null", "bool"],
)
def test_ac9_a_non_object_is_malformed(document: object) -> None:
    assert _code(_bytes(document)) == "malformed_payload"


def test_ac9_deeply_nested_json_is_malformed_not_a_crash() -> None:
    assert _code(b"[" * 100_000 + b"]" * 100_000) == "malformed_payload"


@pytest.mark.parametrize(
    "dataset", ["general_ledger", "Trial_Balance", "", None, 7, ["trial_balance"]]
)
def test_ac9_a_wrong_dataset_is_malformed(dataset: object) -> None:
    assert _code(_with(dataset=dataset)) == "malformed_payload"


def test_ac9_a_missing_dataset_is_malformed() -> None:
    document = _document()
    del document["dataset"]
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("field", ["period", "lines", "control_totals"])
def test_ac9_a_missing_top_level_field_is_malformed(field: str) -> None:
    document = _document()
    del document[field]
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("field", ["period", "lines", "control_totals"])
@pytest.mark.parametrize("value", [None, "text", 5], ids=["null", "string", "int"])
def test_ac9_a_top_level_field_of_the_wrong_shape_is_malformed(field: str, value: object) -> None:
    assert _code(_with(**{field: value})) == "malformed_payload"


@pytest.mark.parametrize("field", ["period", "control_totals"])
def test_ac9_an_array_where_an_object_belongs_is_malformed(field: str) -> None:
    assert _code(_with(**{field: list[object]()})) == "malformed_payload"


def test_ac9_an_object_where_the_lines_list_belongs_is_malformed() -> None:
    assert _code(_with(lines={})) == "malformed_payload"


@pytest.mark.parametrize("field", ["start", "end"])
def test_ac9_a_missing_period_field_is_malformed(field: str) -> None:
    document = _document()
    del cast(dict[str, object], document["period"])[field]
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("value", ["2025-13-01", "yesterday", "", None, 20250101])
def test_ac9_an_unreadable_period_date_is_malformed(value: object) -> None:
    document = _document()
    cast(dict[str, object], document["period"])["start"] = value
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("field", ["id", "code", "name", "debit", "credit"])
def test_ac9_a_missing_line_field_is_malformed(field: str) -> None:
    assert _code(_without_line_field(field)) == "malformed_payload"


@pytest.mark.parametrize("field", ["debit", "credit"])
def test_ac9_a_missing_control_total_is_malformed(field: str) -> None:
    document = _document()
    del cast(dict[str, object], document["control_totals"])[field]
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("line", [None, "text", 5, ["x"]], ids=["null", "string", "int", "array"])
def test_ac9_a_line_that_is_not_an_object_is_malformed(line: object) -> None:
    document = _document()
    _lines(document).append(cast(dict[str, object], line))
    assert _code(_bytes(document)) == "malformed_payload"


@pytest.mark.parametrize("field", ["debit", "credit"])
@pytest.mark.parametrize("value", [100, 100.5, 0, 0.0, True, None, ["1.00"]])
def test_ac9_a_non_string_line_amount_is_malformed_not_an_amount_error(
    field: str, value: object
) -> None:
    assert _code(_with_line(0, **{field: value})) == "malformed_payload"


@pytest.mark.parametrize("field", ["debit", "credit"])
@pytest.mark.parametrize("value", [150, 150.0, None])
def test_ac9_a_non_string_control_total_is_malformed(field: str, value: object) -> None:
    assert _code(_with_totals(**{field: value})) == "malformed_payload"


def test_ac9_a_json_number_amount_never_reaches_float_arithmetic() -> None:
    # 0.1 as a JSON number would be a float; the contract refuses numbers outright.
    assert _code(_with_line(0, debit=0.1)) == "malformed_payload"


@pytest.mark.parametrize("field", ["id", "code", "name"])
@pytest.mark.parametrize(
    "value",
    ["", "x" * 201, "a\nb", "a\tb", "a\x00b", "a\x7fb", "a\x1fb", "a\rb", 5, None],
    ids=["empty", "201-chars", "newline", "tab", "nul", "del", "us", "cr", "int", "null"],
)
def test_ac9_bad_line_text_is_malformed(field: str, value: object) -> None:
    assert _code(_with_line(0, **{field: value})) == "malformed_payload"


@pytest.mark.parametrize("field", ["id", "code", "name"])
def test_ac9_text_of_exactly_200_characters_is_accepted(field: str) -> None:
    tb = parse_trial_balance(_with_line(0, **{field: "x" * 200}))
    assert len(tb.lines) == 2


def test_ac9_ordinary_unicode_text_is_accepted() -> None:
    tb = parse_trial_balance(_with_line(0, name="Caf\u00e9 R\u00e9sum\u00e9 \u00a3"))
    assert tb.lines[0].account_name == "Caf\u00e9 R\u00e9sum\u00e9 \u00a3"


def test_ac9_more_than_50000_lines_is_malformed() -> None:
    document = _document()
    document["lines"] = [
        {"id": f"a{n}", "code": str(n), "name": "n", "debit": "0.00", "credit": "0.00"}
        for n in range(50_001)
    ]
    assert _code(_bytes(document)) == "malformed_payload"


# --- invalid_amount --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "",
        "1,000.00",
        "$1.00",
        "NaN",
        "nan",
        "sNaN",
        "Infinity",
        "-Infinity",
        "inf",
        "-1.00",
        "-0.01",
        "-100",
        "1.001",
        "0.005",
        "12.345",
        "1e15",
        "1000000000000000",
        "1000000000000000.00",
        "1e16",
        "99999999999999999999.00",
    ],
)
@pytest.mark.parametrize("field", ["debit", "credit"])
def test_ac9_a_bad_line_amount_is_invalid_amount(field: str, value: str) -> None:
    assert _code(_with_line(0, **{field: value})) == "invalid_amount"


@pytest.mark.parametrize("field", ["debit", "credit"])
@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity", "-1.00", "1.001", "1e15"])
def test_ac9_a_bad_declared_total_is_invalid_amount(field: str, value: str) -> None:
    assert _code(_with_totals(**{field: value})) == "invalid_amount"


def test_ac9_parse_error_carries_a_short_code_and_is_an_exception() -> None:
    error = NormaliseError("malformed_payload")
    assert isinstance(error, Exception)
    assert error.code == "malformed_payload"


def test_ac9_parsing_does_not_modify_a_document_it_is_given_twice() -> None:
    content = _bytes(_document())
    snapshot = copy.deepcopy(content)
    assert parse_trial_balance(content) == parse_trial_balance(content)
    assert content == snapshot


# --- revision 1: size, encoding, duplicate keys, currency ------------------------------------

MAX_BYTES = 20 * 1024 * 1024


def test_ac9_the_parsed_model_carries_the_currency() -> None:
    assert parse_trial_balance(_bytes(_document())).currency == "USD"


@pytest.mark.parametrize("value", [None, 5, ["USD"], "", "  "])
def test_ac9_a_missing_or_unreadable_currency_is_malformed(value: object) -> None:
    assert _code(_with(currency=value)) == "malformed_payload"
    document = _document()
    del document["currency"]
    assert _code(_bytes(document)) == "malformed_payload"


def test_ac9_a_payload_over_20_mib_is_too_large() -> None:
    assert _code(b" " * (MAX_BYTES + 1)) == "payload_too_large"


def test_ac9_size_is_checked_before_the_content_is_read() -> None:
    assert _code(b"\xff" * (MAX_BYTES + 1)) == "payload_too_large"


def test_ac9_a_payload_of_exactly_20_mib_is_not_too_large() -> None:
    padding = MAX_BYTES - len(_bytes(_document())) - 1
    content = _bytes(_document()) + b" " * padding
    assert len(content) < MAX_BYTES + 1
    assert len(parse_trial_balance(content).lines) == 2


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be", "utf-32"])
def test_ac9_other_encodings_are_refused(encoding: str) -> None:
    assert _code(json.dumps(_document()).encode(encoding)) == "malformed_payload"


def test_ac9_a_utf8_byte_order_mark_is_not_accepted_as_json() -> None:
    assert _code(b"\xef\xbb\xbf" + _bytes(_document())) == "malformed_payload"


def test_ac9_a_duplicate_top_level_key_is_malformed() -> None:
    text = json.dumps(_document())
    assert _code((text[:-1] + ', "dataset": "trial_balance"}').encode()) == "malformed_payload"


def test_ac9_a_duplicate_key_in_a_line_is_malformed() -> None:
    text = json.dumps(_document()).replace(
        '"debit": "150.00",', '"debit": "150.00", "debit": "1.00",', 1
    )
    assert '"debit": "1.00"' in text
    assert _code(text.encode()) == "malformed_payload"


def test_ac9_a_duplicate_key_in_the_period_or_totals_is_malformed() -> None:
    base = json.dumps(_document())
    in_period = base.replace(
        '"start": "2025-01-01"', '"start": "2025-01-01", "start": "2024-01-01"'
    )
    in_totals = base.replace(
        '"control_totals": {"debit": "150.00"',
        '"control_totals": {"debit": "150.00", "debit": "1.00"',
    )
    assert in_period != base
    assert in_totals != base
    assert _code(in_period.encode()) == "malformed_payload"
    assert _code(in_totals.encode()) == "malformed_payload"


def test_ac9_a_duplicate_key_inside_an_ignored_field_is_still_malformed() -> None:
    base = json.dumps(_document())
    assert _code(base.replace('"provider": "fake"', '"x": 1, "x": 2', 1).encode()) == (
        "malformed_payload"
    )


# --- revision 1: text ------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["id", "code", "name"])
@pytest.mark.parametrize(
    "value",
    [
        "a\u200bb",  # zero width space (Cf)
        "a\u200db",  # zero width joiner (Cf)
        "a\ufeffb",  # byte order mark (Cf)
        "a\u202eb",  # right-to-left override (Cf)
        "a\u2066b",  # isolate (Cf)
        "a\ue000b",  # private use (Co)
        "a\u2028b",  # line separator (Zl)
        "a\u2029b",  # paragraph separator (Zp)
        "a\x85b",  # next line (Cc)
        "a\x9fb",  # C1 control (Cc)
        "a\ud800b",  # lone surrogate (Cs)
    ],
    ids=["zwsp", "zwj", "bom", "rlo", "isolate", "private", "zl", "zp", "nel", "c1", "surrogate"],
)
def test_ac9_invisible_or_directional_characters_in_text_are_malformed(
    field: str, value: str
) -> None:
    content = json.dumps(_document() | {"lines": [_lines(_document())[0] | {field: value}]})
    assert _code(content.encode()) == "malformed_payload"


@pytest.mark.parametrize("field", ["id", "code", "name"])
@pytest.mark.parametrize("value", [" ", "   ", "\u00a0", "\u3000"], ids=["1", "3", "nbsp", "ideo"])
def test_ac9_text_that_is_empty_after_trimming_is_malformed(field: str, value: str) -> None:
    assert _code(_with_line(0, **{field: value})) == "malformed_payload"


def test_ac9_text_is_trimmed() -> None:
    tb = parse_trial_balance(_with_line(0, code="  1000  ", name=" Cash "))
    assert (tb.lines[0].account_code, tb.lines[0].account_name) == ("1000", "Cash")


def test_ac9_the_length_limit_applies_after_trimming() -> None:
    assert len(parse_trial_balance(_with_line(0, name=" " + "x" * 200 + " ")).lines) == 2
    assert _code(_with_line(0, name="x" * 201)) == "malformed_payload"


@pytest.mark.parametrize("name", ["Caf\u00e9", "\u4f1a\u8a08", "O'Brien & Sons, Inc.", "A\u0301"])
def test_ac9_ordinary_international_text_is_accepted(name: str) -> None:
    assert parse_trial_balance(_with_line(0, name=name)).lines[0].account_name == name


# --- revision 1: amounts ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "+1.00",
        "1e2",
        "1E2",
        "1_000.00",
        "1 .00",
        " 1.00",
        "1.00 ",
        "\u0661\u0662\u0663",  # Arabic-Indic digits
        "\uff11\uff12",  # fullwidth digits
        "1.",
        ".5",
        "1.5.0",
        "0x10",
        "1,5",
        "1000000000000000",  # 16 digits
        "-0",
        "00000000000000000",
    ],
)
@pytest.mark.parametrize("field", ["debit", "credit"])
def test_ac9_an_amount_that_is_not_plain_ascii_decimal_is_invalid(field: str, value: str) -> None:
    assert _code(_with_line(0, **{field: value})) == "invalid_amount"


@pytest.mark.parametrize(
    "value", ["999999999999999", "0", "0.0", "0.5", "7.25", "123456789012345.67"]
)
def test_ac9_plain_decimals_up_to_15_digits_and_2_places_are_accepted(value: str) -> None:
    tb = parse_trial_balance(_with_line(0, debit=value))
    assert tb.lines[0].debit == Decimal(value).quantize(Decimal("0.01"))
