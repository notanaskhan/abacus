"""T-05-T48 (TASK-7705; T-05 F9, §6.4; TXP-01; DEC-4708): `tax.memo_drafter`'s settlement by code.

Row acceptance: "The fake-model suite passes with number provenance 1.0 and human-edited sections
untouched on regenerate." Here: a number with no provenance is dropped (an empty section reads
Unsupported), unknown citations are dropped, citations carry offsets, a person's section and the
unaffected sections of a regenerate are carried over whatever the model answers.
"""

from __future__ import annotations

from abacus.modules.agents.api import spec_v2
from abacus.modules.tax.memo_drafter import (
    CAPABILITY,
    UNSUPPORTED,
    DraftMemoInput,
    DraftMemoOutput,
    MemoFact,
    MemoSectionOut,
    MemoSegment,
    MemoSource,
    content_hash_of,
    fingerprint_of,
    numbers_in,
    settle,
)

GIVEN = DraftMemoInput(
    entity_name="Ridgeline Property Partners, LP",
    tax_year=2025,
    sections=["balance_sheet", "capital", "open_items"],
    facts=[
        MemoFact(handle="tb_assets", label="Total assets", value="17,914,500"),
        MemoFact(handle="tb_liabilities", label="Liabilities", value="11,048,300"),
        MemoFact(handle="capital", label="Capital", value="6,866,200"),
    ],
    sources=[
        MemoSource(
            handle="cell:01!f18", label="01 Trial Balance", quote="Total assets 17,914,500"
        ),
        MemoSource(handle="doc:harborline", label="Harborline", quote="tax-exempt, 6,200"),
    ],
)


def _answer(*sections: tuple[str, list[tuple[str, list[str]]]]) -> DraftMemoOutput:
    return DraftMemoOutput(
        sections=[
            MemoSectionOut(
                key=key, segments=[MemoSegment(text=t, citations=c) for t, c in segments]
            )
            for key, segments in sections
        ]
    )


def test_numbers_are_read_as_bare_digits() -> None:
    assert numbers_in("Capital of 6,866,200 and 6,200.") == {"6866200", "6200"}


def test_a_number_with_no_provenance_is_dropped_and_an_empty_section_is_unsupported() -> None:
    settled = settle(
        _answer(
            ("balance_sheet", [("Total assets are 17,914,500.", ["cell:01!f18"])]),
            ("capital", [("Capital is 6,900,000.", ["cell:01!f18"])]),
        ),
        GIVEN,
    )
    by_key = {s.key: s for s in settled.sections}
    assert by_key["balance_sheet"].segments[0]["text"] == "Total assets are 17,914,500."
    assert by_key["capital"].unsupported
    assert by_key["capital"].segments == ({"text": UNSUPPORTED, "citations": []},)
    assert ("capital", "number_unsupported") in settled.dropped
    assert by_key["open_items"].unsupported  # nothing drafted for it


def test_a_quoted_number_backs_a_segment_that_cites_it() -> None:
    settled = settle(
        _answer(
            ("capital", [("Tax-exempt interest of 6,200 increases M-2.", ["doc:harborline"])])
        ),
        GIVEN,
    )
    capital = next(s for s in settled.sections if s.key == "capital")
    assert not capital.unsupported
    assert capital.segments[0]["citations"] == [{"n": 2, "start": 0, "end": 44}]


def test_an_unknown_citation_is_dropped_and_offsets_follow_the_text() -> None:
    settled = settle(
        _answer(
            (
                "balance_sheet",
                [
                    ("Total assets are 17,914,500.", ["cell:01!f18", "doc:invented"]),
                    ("Liabilities are 11,048,300.", []),
                ],
            )
        ),
        GIVEN,
    )
    bs = next(s for s in settled.sections if s.key == "balance_sheet")
    first, second = bs.segments
    assert first["citations"] == [{"n": 1, "start": 0, "end": 28}]
    assert second["citations"] == []
    assert ("balance_sheet", "citation_unknown") in settled.dropped


def test_a_persons_section_and_unaffected_sections_are_untouched_on_regenerate() -> None:
    human = {
        "capital": {
            "key": "capital",
            "segments": [{"text": "Olivia's note: capital reconciles.", "citations": []}],
            "human_owned": True,
        }
    }
    previous = {
        **human,
        "balance_sheet": {
            "key": "balance_sheet",
            "segments": [{"text": "Total assets are 17,914,500.", "citations": []}],
            "human_owned": False,
        },
    }
    settled = settle(
        _answer(
            ("capital", [("Capital is 6,866,200.", [])]),
            ("balance_sheet", [("Rewritten 11,048,300.", [])]),
            ("open_items", [("No open items remain on capital.", [])]),
        ),
        GIVEN,
        human_owned=human,
        affected=["open_items"],
        previous=previous,
    )
    by_key = {s.key: s for s in settled.sections}
    assert by_key["capital"].human_owned
    assert by_key["capital"].segments[0]["text"] == "Olivia's note: capital reconciles."
    assert by_key["balance_sheet"].segments[0]["text"] == "Total assets are 17,914,500."
    assert by_key["open_items"].segments[0]["text"] == "No open items remain on capital."
    assert settled.number_provenance == 1.0


def test_hashes_are_stable_and_follow_the_figures() -> None:
    settled = settle(_answer(("capital", [("Capital is 6,866,200.", [])])), GIVEN)
    assert content_hash_of(settled.sections) == content_hash_of(settled.sections)
    moved = GIVEN.model_copy(
        update={"facts": [MemoFact(handle="capital", label="Capital", value="6,860,000")]}
    )
    assert fingerprint_of(GIVEN.facts) != fingerprint_of(moved.facts)


def test_the_spec_is_a_tool_less_workflow_on_tri_with_its_suite() -> None:
    spec = spec_v2(CAPABILITY)
    assert spec.prompt == "tax.preparer_memo@v1"
    assert spec.autonomy == "propose"
    assert "tri" in spec.data_classes
    assert spec.evaluation_suite == "evals/tax_memo_drafter"
