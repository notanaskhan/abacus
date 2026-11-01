"""K-01-T20: the methodology importer's isolated extraction and its PII hold (DEC-1855).

Row acceptance (second half): "a file with SSN patterns is held with no model call." The hold is
code over the isolated child's words; nothing here can reach `ai_gateway`.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from abacus.kernel.pdf_pages import PageWords, Word
from abacus.modules.methodology import extraction
from abacus_tools.synthetic.documents import encrypted_pdf, positioned_pdf


def _page(n: int, text: str) -> PageWords:
    return PageWords(n, tuple(Word(t, (0.1, 0.1, 0.2, 0.2)) for t in text.split()))


def test_a_page_with_an_ssn_holds_the_file_and_names_only_the_page() -> None:
    hold = extraction.pii_hold(
        [_page(1, "Plan sponsor review"), _page(2, "SSN 512-34-6789 on file")]
    )
    assert hold.held
    assert hold.pages == (2,)
    assert "ssn" in hold.forms
    assert "6789" not in repr(hold)


def test_clean_pages_are_not_held() -> None:
    assert extraction.pii_hold([_page(1, "BH-EBP-110 step 7"), _page(2, "AU-C 320")]) == (
        extraction.PiiHold(False)
    )


async def test_extract_source_holds_an_ssn_pdf_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import abacus.ai_gateway as gateway

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("no model call before the PII hold")

    monkeypatch.setattr(gateway, "call", refuse)
    content = positioned_pdf(
        [[(72, 720, "Participant census excerpt")], [(72, 720, "SSN 512-34-6789")]]
    )
    found = await extraction.extract_source(content)
    assert found.page_count == 2
    assert found.hold.held and found.hold.pages == (2,)


async def test_extract_source_raises_the_problem_codes() -> None:
    with pytest.raises(extraction.SourceEncrypted):
        await extraction.extract_source(encrypted_pdf())
    with pytest.raises(extraction.SourceMalformed):
        await extraction.extract_source(b"not a pdf")


def test_the_extraction_module_never_imports_the_gateway() -> None:
    tree = ast.parse(inspect.getsource(extraction))
    names = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names
    }
    assert not any(n.startswith(("abacus.ai_gateway", "abacus.modules.agents")) for n in names)
