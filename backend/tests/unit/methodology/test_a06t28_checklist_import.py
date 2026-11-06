"""A-06-T28 (TASK-3339; DEC-2373): the checklist file's grammar and the slice's 142 items."""

from __future__ import annotations

from abacus.modules.methodology.disclosure_checklists import MAX_BYTES, parse_items
from abacus_tools.synthetic.scenarios.brightwater_hale.completion_slice import ITEMS, checklist_csv


def test_ac_the_slice_is_142_items_with_no_problem() -> None:
    items, problems = parse_items(checklist_csv())
    assert (len(items), problems) == (ITEMS, [])
    assert ITEMS == 142
    assert len({i["key"] for i in items}) == 142


def test_a_bad_row_is_named_by_where_it_is_never_its_text() -> None:
    body = b"key,section,text\nBad Key,General,Hostile text\ndc_1,General,\ndc_1,General,Twice\n"
    _, problems = parse_items(body)
    assert problems == ["row 2: key", "row 3: text", "row 4: duplicate_key"]
    assert not any("Hostile" in p for p in problems)


def test_a_file_that_is_not_a_checklist_is_refused() -> None:
    assert parse_items(b"\xff\xfe\x00")[1] == ["not_csv"]
    assert parse_items(b"key,section,text\n")[1] == ["empty"]
    assert parse_items(b"x" * (MAX_BYTES + 1))[1] == ["too_large"]
