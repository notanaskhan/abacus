"""T-01-T19 (TASK-2317; T-01 §3.9, §3.10; DEC-1363): the CCH file adapter parses the engine's
values and diagnostics files (tax-engine-bridge.md §6), refuses anything else by code and never
by its content, and computes the differences against Accrued by code: TAX-09's Feld V3 file yields
its five differing fields and nothing else."""

from __future__ import annotations

import pytest

from abacus.modules.tax import engine_adapter as adapter

HEAD = "return_id,version,field_key,form,line,value\n"
FELD_V3 = (
    HEAD
    + "2025I:FeldJ,V3,co_dr0104pn.co_source_income,DR 0104PN,34,96989\n"
    + "2025I:FeldJ,V3,f1040.direct_deposit_last4,1040,35b,6620\n"
    + "2025I:FeldJ,V3,f1040.refund,1040,35a,253\n"
    + "2025I:FeldJ,V3,f1040.total_tax,1040,24,123223.00\n"
    + "2025I:FeldJ,V3,f1040es_2026.voucher_amount,1040-ES,Q1-Q4,19990\n"
    + "2025I:FeldJ,V3,f8879.signature_method,8879,Part II,practitioner_pin\n"
    + "2025I:FeldJ,V3,il1040_schnr.il_source_income,IL-1040 Sch NR,47,141634\n"
).encode()
ACCRUED: dict[str, dict[str, object]] = {
    "f1040.refund": {"t": "decimal", "v": "253"},
    "f1040.total_tax": {"t": "decimal", "v": "123223"},
    "f1040.other": {"t": "decimal", "v": "9"},
}


def test_ac_values_parse_with_their_return_and_version() -> None:
    parsed = adapter.parse_values(FELD_V3)
    assert (parsed.engine_return_id, parsed.version) == ("2025I:FeldJ", 3)
    assert [r.field_key for r in parsed.rows] == sorted(r.field_key for r in parsed.rows)


def test_ac_the_feld_v3_file_differs_in_five_fields_and_changes_nothing_else() -> None:
    rows = adapter.differences(ACCRUED, adapter.parse_values(FELD_V3))
    assert [(r.field_key, r.cause_code) for r in rows] == [
        ("co_dr0104pn.co_source_income", "engine_only"),
        ("f1040.direct_deposit_last4", "engine_only"),
        ("f1040es_2026.voucher_amount", "engine_only"),
        ("f8879.signature_method", "engine_only"),
        ("il1040_schnr.il_source_income", "engine_only"),
    ]
    # 123223.00 equals 123223; a field the engine file does not name is left alone.
    assert all(r.field_key not in ("f1040.total_tax", "f1040.other") for r in rows)


def test_a_changed_value_is_an_engine_value_difference() -> None:
    accrued: dict[str, dict[str, object]] = {
        **ACCRUED,
        "f1040.refund": {"t": "decimal", "v": "250"},
    }
    rows = adapter.differences(accrued, adapter.parse_values(FELD_V3))
    refund = next(r for r in rows if r.field_key == "f1040.refund")
    assert (refund.cause_code, refund.accrued, refund.engine) == (
        "engine_value",
        {"t": "decimal", "v": "250"},
        {"t": "decimal", "v": "253"},
    )


def test_cells_are_typed() -> None:
    assert adapter.typed("19,990") == {"t": "decimal", "v": "19990"}
    assert adapter.typed("practitioner_pin") == {"t": "text", "v": "practitioner_pin"}
    assert adapter.typed("NaN") == {"t": "text", "v": "NaN"}


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"\xff\xfe", "not_utf8"),
        (b"a,b\n1,2\n", "unknown_header"),
        (HEAD.encode(), "empty"),
        (
            (HEAD + "2025I:FeldJ,V3,a,1040,1,1\n2025I:OtherX,V3,b,1040,1,1\n").encode(),
            "mixed_returns",
        ),
        ((HEAD + "FeldJ,V3,a,1040,1,1\n").encode(), "bad_return_id"),
        ((HEAD + "2025I:FeldJ,3,a,1040,1,1\n").encode(), "bad_return_id"),
        ((HEAD + "2025I:FeldJ,V3,a b,1040,1,1\n").encode(), "bad_row"),
        (
            (HEAD + "2025I:FeldJ,V3,a,1040,1,1\n2025I:FeldJ,V3,a,1040,1,2\n").encode(),
            "duplicate_field",
        ),
    ],
)
def test_a_file_that_is_not_the_engines_is_refused_by_code(content: bytes, code: str) -> None:
    with pytest.raises(adapter.EngineFileInvalid) as raised:
        adapter.parse_values(content)
    assert raised.value.code == code


def test_diagnostics_parse_with_severity() -> None:
    content = (
        b"return_id,version,severity,code,form,field_key,message\n"
        b"2025I:FeldJ,V3,error,EF-IPPIN-01,1040,f1040.ip_pin_primary,"
        b"Identity Protection PIN required for the primary taxpayer\n"
        b"2025I:FeldJ,V3,informational,8995A-UBIA,8995-A,,UBIA from Statement A used\n"
    )
    parsed = adapter.parse_diagnostics(content)
    assert [(d.severity, d.field_key) for d in parsed.diagnostics] == [
        ("error", "f1040.ip_pin_primary"),
        ("informational", None),
    ]
    with pytest.raises(adapter.EngineFileInvalid):
        adapter.parse_diagnostics(content.replace(b"informational", b"fatal"))
