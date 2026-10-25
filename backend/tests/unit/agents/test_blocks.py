"""P-09-T03 (TASK-5004): AgentBlocks v1 validates only safe, closed, referenced output."""

from __future__ import annotations

from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.agents.blocks import (
    AgentBlocks,
    BlocksRejected,
    Fact,
    lint_text,
    validate_blocks,
)

CITE = UUID(int=11)
FACTS = {
    "tb_total": Fact(
        id="tb_total", kind="money", value="16812400.00", basis="trial_balance:final"
    ),
    "participants": Fact(id="participants", kind="count", value="286", basis="census:rows"),
}


def _p(*segments: dict[str, object]) -> dict[str, object]:
    return {"parts": [{"kind": "p", "segments": list(segments)}]}


def _code(payload: dict[str, object]) -> str:
    with pytest.raises(BlocksRejected) as raised:
        validate_blocks(payload, FACTS, {CITE})
    return raised.value.code


def test_ac1_a_paragraph_with_facts_and_cites_validates() -> None:
    blocks = validate_blocks(
        _p(
            {"kind": "text", "text": "Trial Balance agrees to the net trust assets of "},
            {"kind": "fact", "fact_id": "tb_total"},
            {"kind": "text", "text": " across the 401(k) plan's participants "},
            {"kind": "cite", "citation_id": str(CITE), "n": 1},
        ),
        FACTS,
        {CITE},
    )
    assert isinstance(blocks, AgentBlocks)
    assert blocks.parts[0].kind == "p"


def test_ac1_every_part_kind_validates() -> None:
    payload = {
        "parts": [
            {
                "kind": "table",
                "head": ["Account", "Balance"],
                "rows": [
                    [
                        {"kind": "text", "text": "Investments"},
                        {"kind": "fact", "fact_id": "tb_total"},
                    ]
                ],
            },
            {
                "kind": "kv",
                "rows": [
                    {"label": "Read", "value": [{"kind": "fact", "fact_id": "participants"}]}
                ],
            },
            {"kind": "metric", "label": "Participants", "fact_id": "participants"},
            {"kind": "file", "artifact_id": str(UUID(int=3)), "name": "Census workbook"},
            {"kind": "badge", "object": "engagement", "code": "active"},
            {"kind": "cite_list", "cites": [{"kind": "cite", "citation_id": str(CITE), "n": 1}]},
            {
                "kind": "options",
                "options": [
                    {"key": "run", "title": "Run the plan", "recommended": True},
                    {"key": "change", "title": "Change the order"},
                ],
            },
            {"kind": "entity_ref", "record_type": "workpaper", "record_id": str(UUID(int=4))},
        ]
    }
    assert len(validate_blocks(payload, FACTS, {CITE}).parts) == 8


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("The total is $16,812,400.00", "free_number"),
        ("about 286 participants", "free_number"),
        ("ninety percent sure", "free_number"),
        ("I approved the entry", "human_act"),
        ("The reviewer signed off", "human_act"),
        ("I decided to post it", "human_act"),
        ("Reminders sent to the client", "human_act"),
        ("All done!", "exclamation"),
        ("I learned this from memory", "banned_word"),
        ("<b>bold</b>", "markup"),
        ("**bold**", "markup"),
        ("see [here](https://evil.example)", "link"),
        ("visit https://evil.example/x", "link"),
    ],
)
def test_ac2_the_copy_lint_refuses(text: str, code: str) -> None:
    assert _code(_p({"kind": "text", "text": text})) == code


def test_ac2_names_with_digits_are_not_figures() -> None:
    lint_text("the 401(k) plan's W2 forms for Q4", "x")


def test_ac3_references_must_be_registered() -> None:
    assert _code(_p({"kind": "fact", "fact_id": "made_up"})) == "unknown_fact"
    assert (
        _code(_p({"kind": "cite", "citation_id": str(UUID(int=99)), "n": 1})) == "unknown_citation"
    )
    assert (
        _code({"parts": [{"kind": "badge", "object": "engagement", "code": "approved_by_ai"}]})
        == "unknown_status"
    )


def test_ac3_closed_union_and_limits() -> None:
    assert _code({"parts": [{"kind": "html", "html": "<p>x</p>"}]}) == "shape"
    assert _code({"parts": []}) == "shape"
    assert (
        _code({"parts": [{"kind": "p", "segments": [{"kind": "text", "text": "x", "extra": 1}]}]})
        == "shape"
    )
    options = [{"key": f"k{i}", "title": "One", "recommended": True} for i in ("a", "b")]
    assert _code({"parts": [{"kind": "options", "options": options}]}) == "two_recommended"


@settings(max_examples=200, deadline=None)
@given(
    prefix=st.text(alphabet="abcdefghij ", max_size=20),
    figure=st.from_regex(r"\$?[1-9][0-9]{0,6}(\.[0-9]{2})?%?", fullmatch=True),
)
def test_property_no_free_number_ever_validates(prefix: str, figure: str) -> None:
    with pytest.raises(BlocksRejected):
        validate_blocks(_p({"kind": "text", "text": f"{prefix} {figure} "}), FACTS, {CITE})


@settings(max_examples=200, deadline=None)
@given(
    tag=st.sampled_from(["b", "i", "script", "a href=x", "img src=y", "div"]),
    body=st.text(max_size=10),
)
def test_property_no_markup_ever_validates(tag: str, body: str) -> None:
    with pytest.raises(BlocksRejected):
        validate_blocks(_p({"kind": "text", "text": f"<{tag}>{body or 'x'}"}), FACTS, {CITE})
