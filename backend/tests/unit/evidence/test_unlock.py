"""TASK-323: a password-protected PDF is unlocked once with its password; the copy reads."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from abacus.modules.evidence.checks import ExtractedFields, readable
from abacus.modules.evidence.extraction import PDF, extract
from abacus.modules.evidence.unlock import remove_password
from abacus_tools.synthetic.documents import bank_statement_pdf

# A synthetic statement encrypted with AES-256 (qpdf), user password "statement2026".
LOCKED = (Path(__file__).parent / "fixtures" / "locked_statement.pdf").read_bytes()


def test_a_locked_statement_is_unreadable_as_encrypted() -> None:
    found = extract(LOCKED, PDF)
    assert (found.status, found.reason) == ("unreadable", "encrypted")


def test_the_right_password_gives_a_copy_that_reads() -> None:
    outcome, plain = remove_password(LOCKED, "statement2026")
    assert outcome == "unlocked"
    found = extract(plain, PDF)
    assert found.status == "extracted"
    assert found.statement is not None and found.statement.closing == Decimal("12124.50")


def test_a_wrong_password_unlocks_nothing() -> None:
    assert remove_password(LOCKED, "nope") == ("wrong_password", b"")


def test_an_unlocked_or_damaged_file_is_not_unlocked() -> None:
    assert remove_password(bank_statement_pdf(), "x")[0] == "not_locked"
    assert remove_password(b"%PDF-1.4\nnot a pdf", "x")[0] == "damaged"


def test_needs_ocr_is_not_a_client_problem() -> None:
    fields = ExtractedFields(
        "not_extracted", "needs_ocr", None, None, None, None, None, None, None, None
    )
    found = readable(fields)
    assert (found.outcome, found.reason) == ("not_applicable", "needs_ocr")
