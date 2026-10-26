"""P-03-T19: the unlock's isolated child, in process. It decrypts, reads the word layer, scans it
with the upload's own scan and renders masked pages; nothing else leaves it."""

from __future__ import annotations

import pypdfium2
import pytest

from abacus.modules.evidence.unlock import derive_unlocked
from abacus_tools.synthetic.documents import bank_statement_pdf, password_pdf

OPENS_WITH = "halvard-2025"


def test_password_pdf_opens_only_with_its_password() -> None:
    locked = password_pdf(OPENS_WITH)
    with pytest.raises(pypdfium2.PdfiumError):
        pypdfium2.PdfDocument(locked)
    assert derive_unlocked(locked, OPENS_WITH).outcome == "unlocked"


def test_the_right_password_gives_scanned_masked_pages() -> None:
    derived = derive_unlocked(password_pdf(OPENS_WITH), OPENS_WITH)
    assert derived.outcome == "unlocked"
    assert derived.scanned == (1,) and derived.unscannable == ()
    assert sorted((f.kind, f.last4) for f in derived.found) == [("ein", "4321"), ("ssn", "3456")]
    assert derived.rendered is not None and derived.rendered.kind == "pages"
    assert all(p.png.startswith(b"\x89PNG") for p in derived.rendered.pages)
    # The Derived record carries no decrypted file: only words, regions and masked images.
    assert not any(isinstance(v, bytes) and v.startswith(b"%PDF") for v in vars(derived).values())


def test_a_wrong_password_or_an_unlocked_file_derives_nothing() -> None:
    assert derive_unlocked(password_pdf(OPENS_WITH), "nope").outcome == "wrong_password"
    assert derive_unlocked(bank_statement_pdf(), "x").outcome == "not_locked"
    assert derive_unlocked(b"%PDF-1.4\nbroken", "x").outcome == "damaged"
