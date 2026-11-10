"""DEC-2392: what a person wrote over any top-level block is what the document says."""

from __future__ import annotations

from abacus.modules.reporting.compose import block_texts, compose

_BODY: list[object] = [
    {"type": "paragraph", "runs": [{"type": "text", "text": "Template paragraph"}]},
    {"type": "clause", "clause_id": "agree", "enabled": True, "blocks": []},
    {"type": "section", "id": "s", "blocks": []},
]
_CLAUSES: list[object] = [
    {
        "clause_id": "agree",
        "standard": [{"type": "paragraph", "runs": [{"type": "text", "text": "We agree"}]}],
        "default_enabled": True,
    }
]


def _words(overrides: dict[str, list[str]]) -> str:
    composed = compose(
        layout_key="notice_response",
        body=_BODY,
        clauses=_CLAUSES,
        snapshot={"variables": {}, "clauses": {"agree": True}, "overrides": overrides},
    )
    return " ".join(text for _key, _clause, text in block_texts(composed))


def test_ac_no_override_leaves_the_template() -> None:
    assert _words({}).startswith("Template paragraph We agree")


def test_ac_a_clause_and_a_paragraph_take_what_the_person_wrote() -> None:
    words = _words({"block:1": ["Mine"], "clause:agree": ["Also mine"]})
    assert "Mine" in words and "Also mine" in words
    assert "Template paragraph" not in words and "We agree" not in words


def test_ac_a_section_still_overrides_by_its_own_id() -> None:
    assert "Section text" in _words({"s": ["Section text"]})
