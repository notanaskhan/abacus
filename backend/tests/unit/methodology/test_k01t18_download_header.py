"""K-01-T18 review (DEC-1759): the original-file download names the file safely.

The name is a person's upload (control characters already stripped). A quote or backslash would
break the header's quoting, and a non-Latin-1 character (an em dash, an accent) cannot be encoded
in a header at all; the ASCII fallback and the RFC 5987 `filename*` carry both.
"""

from __future__ import annotations

from abacus.modules.methodology.import_routes import (
    _attachment,  # pyright: ignore[reportPrivateUsage] -- the header writer under test
)
from abacus.modules.methodology.imports import EXTENSION_OF


def test_a_plain_name_is_kept() -> None:
    header = _attachment("BH EBP v3.xlsx")
    assert header == "attachment; filename=\"BH EBP v3.xlsx\"; filename*=UTF-8''BH%20EBP%20v3.xlsx"


def test_quotes_and_non_latin_names_cannot_break_the_header() -> None:
    header = _attachment('Méthodologie — "v3".docx')
    header.encode("latin-1")  # a header Starlette can send
    fallback = header.split(";")[1]
    assert fallback == ' filename="M_thodologie _ _v3_.docx"'
    assert header.endswith("filename*=UTF-8''M%C3%A9thodologie%20%E2%80%94%20%22v3%22.docx")


def test_each_role_names_its_extension() -> None:
    assert EXTENSION_OF == {"document_docx": ".docx", "document_pdf": ".pdf", "workbook": ".xlsx"}
