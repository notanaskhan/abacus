"""K-01-T18 (K-01 §3.6 AC6.1; KNW-02 c): the seeded EBP v3 diffs against v2 as 4 added, 9 changed,
1 removed and 54 unchanged, on every run, by lineage (step key, then program, number and similar
text). The workbooks are the Brightwater Hale loader's; keys are assigned as the import does."""

from __future__ import annotations

from abacus.modules.methodology.diff import StepRow, lineage_diff, normalised
from abacus.modules.methodology.repository import assign_step_keys
from abacus.modules.methodology.workbook import Methodology, parse_workbook
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import spec_of, workbook

FIELDS = ("text", "assertions", "standard_refs", "level", "mandatory", "lock_note")


def _rows(parsed: Methodology, prior: dict[tuple[str, int], str]) -> list[StepRow]:
    keys = assign_step_keys(parsed.steps, prior)
    return [
        StepRow(key, s.program_code, s.number, {f: getattr(s, f) for f in FIELDS})
        for s, key in zip(parsed.steps, keys, strict=True)
    ]


def _v2_v3() -> tuple[list[StepRow], list[StepRow]]:
    v2 = _rows(parse_workbook(workbook(spec_of("ebp", 2)), programs=True), {})
    prior = {(r.program_code, r.number): r.step_key for r in v2}
    v3 = _rows(parse_workbook(workbook(spec_of("ebp", 3)), programs=True), prior)
    return v2, v3


def test_ac6_1_v3_against_v2_is_4_9_1_54() -> None:
    v2, v3 = _v2_v3()
    assert (len(v2), len(v3)) == (64, 67)
    d = lineage_diff(v2, v3)
    assert (d.added, d.changed, d.removed, d.unchanged) == (4, 9, 1, 54)
    assert d.added + d.changed + d.unchanged == 67
    assert d.removed + d.changed + d.unchanged == 64
    added = sorted((r.program_code, r.number) for r in d.rows if r.kind == "added")
    assert added == [("BH-EBP-110", 16), ("BH-EBP-140", 8), ("BH-EBP-410", 10), ("BH-EBP-510", 7)]
    removed = [(r.program_code, r.number) for r in d.rows if r.kind == "removed"]
    assert removed == [("BH-EBP-310", 9)]
    changed = [r for r in d.rows if r.kind == "changed"]
    assert {(r.program_code, r.number) for r in changed} >= {
        ("BH-EBP-110", 7),
        ("BH-EBP-110", 9),
        ("BH-EBP-110", 10),
    }
    for r in changed:
        assert r.changed_fields == ("text",)
        assert r.before_text is not None and r.after_text is not None
        assert r.before_text != r.after_text


def test_ac6_1_the_same_inputs_always_give_the_same_diff() -> None:
    v2, v3 = _v2_v3()
    first = lineage_diff(v2, v3)
    assert all(lineage_diff(v2, v3) == first for _ in range(5))
    assert lineage_diff(list(reversed(v2)), list(reversed(v3))) == first


def test_a_rekeyed_step_in_its_place_with_its_words_is_the_same_step() -> None:
    before = [StepRow("old-key", "P", 3, {"text": "Inspect the  plan document"})]
    after = [StepRow("new-key", "P", 3, {"text": "inspect the plan document."})]
    d = lineage_diff(before, after)
    assert (d.added, d.changed, d.removed) == (0, 1, 0)
    elsewhere = [StepRow("new-key", "P", 4, {"text": "inspect the plan document."})]
    moved = lineage_diff(before, elsewhere)
    assert (moved.added, moved.removed) == (1, 1)


def test_numbering_alone_is_not_a_change() -> None:
    before = [StepRow("k", "P", 3, {"text": "Same"})]
    after = [StepRow("k", "P", 4, {"text": "Same"})]
    d = lineage_diff(before, after)
    assert (d.changed, d.unchanged) == (0, 1)


def test_normalised_text_is_nfkc_casefolded_and_spaced() -> None:
    assert normalised("\uff21\uff22\uff23  Step\n2") == "abc step 2"
