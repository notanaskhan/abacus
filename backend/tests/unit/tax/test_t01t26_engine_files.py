"""T-01-T26 (TASK-2416; T-01 §3.10; tax-engine-bridge §6; DEC-1464): the engine's PDFs and e-file
status report, parsed from the fake engine's files (the partner-validated samples join these
once filed, F-09-T120): every PDF kind by its name, a rejection with its code, only a last four
ever read, and hostile or foreign files refused with a reason code.
"""

from __future__ import annotations

import pytest

from abacus.modules.tax.engine_adapter import (
    PDF_KINDS,
    EngineFileInvalid,
    parse_acks,
    parse_pdf,
)
from abacus_tools.fakes.cch_axcess import CchAxcessFake, Export, conformance

FELD = Export("2025I:FeldJ", 2025, "1040", ())


def test_every_pdf_the_engine_produces_is_read_by_its_name() -> None:
    files = CchAxcessFake().pdf_files(FELD, 3)
    kinds = set()
    for name, content in files.items():
        assert conformance(name, content) == []
        pdf = parse_pdf(name, content)
        assert (pdf.engine_return_id, pdf.version) == ("2025I:FeldJ", 3)
        kinds.add(pdf.kind)
    assert kinds == set(PDF_KINDS)


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("2025I_FeldJ_V3_k1.pdf", b"<html>not a pdf</html>", "not_a_pdf"),
        ("2025I_FeldJ_V3_payroll.pdf", b"%PDF-1.7\n%%EOF", "unknown_pdf_kind"),
        ("../../etc/passwd.pdf", b"%PDF-1.7\n%%EOF", "bad_pdf_name"),
    ],
)
def test_a_foreign_pdf_is_refused(name: str, content: bytes, code: str) -> None:
    with pytest.raises(EngineFileInvalid) as refused:
        parse_pdf(name, content)
    assert refused.value.code == code


def test_the_status_report_keeps_a_rejection_and_only_last_fours() -> None:
    fake = CchAxcessFake()
    accepted = parse_acks(fake.efile_status_file(FELD, "accepted"))
    assert accepted.engine_return_id == "2025I:FeldJ"
    assert {a.status for a in accepted.acks} == {"accepted"}
    assert all(len(a.submission_last4) == 4 for a in accepted.acks)
    rejected = parse_acks(fake.efile_status_file(FELD, "rejected"))
    refused = [a for a in rejected.acks if a.status == "rejected"]
    assert refused and all(a.reject_code for a in refused)


def test_a_hostile_status_report_is_refused() -> None:
    head = b"return_id,jurisdiction,submission_last4,status,status_at,reject_code,reject_text\n"
    full_id = head + b"2025I:FeldJ,federal,12345678901234567890,accepted,2026-09-18,,\n"
    with pytest.raises(EngineFileInvalid):
        parse_acks(full_id)  # a whole submission id is never read (R-04)
    no_code = head + b"2025I:FeldJ,federal,2614,rejected,2026-09-18,,R0000-500\n"
    with pytest.raises(EngineFileInvalid):
        parse_acks(no_code)
