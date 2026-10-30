"""T-01-T22 (TASK-2316; DEC-1362): the fake CCH Axcess reads Accrued's export workbook and emits
the engine's files deterministically; V3 differs from Accrued in exactly TAX-09's five fields; the
diagnostics, PDFs and e-file status report carry the seed's figures; every file passes the same
conformance check the partner sample files will; and it refuses outside a synthetic firm in a
synthetic environment."""

from __future__ import annotations

import csv
import io
import uuid
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus_tools.fakes import cch_axcess as cch
from abacus_tools.fakes.cch_axcess import EngineValue

ACCRUED = [
    EngineValue("f1040.total_tax", "1040", "24", "123223"),
    EngineValue("f1040.payments", "1040", "33", "123476"),
    EngineValue("f1040.refund", "1040", "35a", "253"),
    EngineValue("it201.balance_due", "IT-201", "80", "1269"),
]
FAKE = cch.CchAxcessFake()


def _export(return_id: str = cch.FELD) -> cch.Export:
    return cch.read_export(cch.sample_export(return_id, 2025, "1040", ACCRUED))


def _rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode())))


def test_it_reads_the_export_workbook() -> None:
    export = _export()
    assert (export.return_id, export.tax_year, export.form) == (cch.FELD, 2025, "1040")
    assert {f.field_key for f in export.fields} == {f.field_key for f in ACCRUED}


def test_a_workbook_without_the_export_sheets_is_refused() -> None:
    with pytest.raises(cch.ExportUnreadable):
        cch.read_export(b"not a workbook")


def test_v3_differs_from_accrued_in_exactly_tax09s_five_fields() -> None:
    export = _export()
    accrued = {f.field_key: f.value for f in ACCRUED}
    v2 = {v.field_key: v.value for v in FAKE.values(export, 2)}
    v3 = {v.field_key: v.value for v in FAKE.values(export, 3)}
    new_in_v3 = {k: v for k, v in v3.items() if k not in v2}
    assert new_in_v3 == {
        "f1040es_2026.voucher_amount": "19990",
        "f1040.direct_deposit_last4": "6620",
        "f8879.signature_method": "practitioner_pin",
        "il1040_schnr.il_source_income": "141634",
        "co_dr0104pn.co_source_income": "96989",
    }
    assert all(v3[k] == v for k, v in accrued.items())
    assert FAKE.engine_id(export, 3) == "2025I:FeldJ:V3"


def test_the_payment_figures_foot_to_tax12() -> None:
    v3 = {v.field_key: int(v.value) for v in FAKE.values(_export(), 3) if v.value.isdigit()}
    assert v3["f1040.payments"] - v3["f1040.total_tax"] == v3["f1040.refund"] == 253
    assert v3["it201.tax"] - v3["it201.payments"] == v3["it201.balance_due"] == 1269
    assert v3["il1040.tax"] - v3["il1040.ptet_credit"] == v3["il1040.balance_due"] == 0
    assert (v3["co_dr0104pn.ptet_credit"], v3["it2105_2026.voucher_amount"]) == (4268, 7824)


def test_an_unknown_return_gets_back_only_what_it_exported() -> None:
    export = _export("2025I:OtherX")
    assert FAKE.values(export, 3) == tuple(sorted(export.fields, key=lambda f: f.field_key))


def test_every_file_is_deterministic_and_conforms() -> None:
    export = _export()
    files = {
        "values.csv": FAKE.values_file(export, 3),
        "diagnostics.csv": FAKE.diagnostics_file(export, 3, "informational"),
        "ip_pin.csv": FAKE.diagnostics_file(export, 3, "ip_pin"),
        "accepted.csv": FAKE.efile_status_file(export, "accepted"),
        "rejected.csv": FAKE.efile_status_file(export, "rejected"),
        **FAKE.pdf_files(export, 3),
    }
    again = {
        "values.csv": FAKE.values_file(_export(), 3),
        "diagnostics.csv": FAKE.diagnostics_file(_export(), 3, "informational"),
        "ip_pin.csv": FAKE.diagnostics_file(_export(), 3, "ip_pin"),
        "accepted.csv": FAKE.efile_status_file(_export(), "accepted"),
        "rejected.csv": FAKE.efile_status_file(_export(), "rejected"),
        **FAKE.pdf_files(_export(), 3),
    }
    assert files == again
    assert cch.sample_export(cch.FELD, 2025, "1040", ACCRUED) == cch.sample_export(
        cch.FELD, 2025, "1040", ACCRUED
    )
    for name, content in files.items():
        assert cch.conformance(name, content) == [], name
    assert len([n for n in files if n.endswith(".pdf")]) == len(cch.PDF_KINDS)


def test_conformance_catches_a_broken_file() -> None:
    bad = cch.VALUES_HEADER
    assert cch.conformance("x.csv", ",".join(bad).encode() + b"\na,v3,,1040,1,2\n") != []
    assert cch.conformance("x.csv", b"what,ever\n") == ["unknown header"]
    assert cch.conformance("x.pdf", b"nope") == ["not a PDF"]


def test_diagnostics_variants_match_tax09d() -> None:
    notes = _rows(FAKE.diagnostics_file(_export(), 3, "informational"))
    assert [r["severity"] for r in notes] == ["informational", "informational"]
    errors = [
        r for r in _rows(FAKE.diagnostics_file(_export(), 3, "ip_pin")) if r["severity"] == "error"
    ]
    assert len(errors) == 1 and "Identity Protection PIN" in errors[0]["message"]


def test_the_efile_report_matches_tax12d() -> None:
    accepted = _rows(FAKE.efile_status_file(_export(), "accepted"))
    assert [r["jurisdiction"] for r in accepted] == ["federal", "IL", "CO", "NY"]
    assert accepted[0]["submission_last4"] == "2614"
    rejected = _rows(FAKE.efile_status_file(_export(), "rejected"))
    assert rejected[0]["reject_code"] == "IND-181-01"


async def test_it_refuses_outside_a_synthetic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cch, "settings", lambda: SimpleNamespace(environment="production"))
    with pytest.raises(cch.FakeCchRefused):
        await cch.cch_for(TenantContext(uuid.uuid4(), "system", "test"))


async def test_it_refuses_a_firm_that_is_not_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    async def real(tenant: TenantContext) -> bool:
        return False

    monkeypatch.setattr(cch, "settings", lambda: SimpleNamespace(environment="test"))
    monkeypatch.setattr(cch, "is_synthetic_firm", real)
    with pytest.raises(cch.FakeCchRefused):
        await cch.cch_for(TenantContext(uuid.uuid4(), "system", "test"))
