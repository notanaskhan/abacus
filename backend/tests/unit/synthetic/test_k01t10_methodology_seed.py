"""K-01-T10: Brightwater Hale's methodology seed foots (golden counts; DEC-652). Pure: the
workbooks the slice imports parse to the shapes KNW-02 shows."""

from __future__ import annotations

from abacus.modules.methodology.workbook import parse_workbook
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import (
    VERSIONS,
    methodology_events,
    spec_of,
    workbook,
)


def test_ebp_v3_foots_16_8_6_8_10_7_12_and_21_mandatory() -> None:
    parsed = parse_workbook(workbook(spec_of("ebp", 3)), programs=True)
    per = [sum(1 for s in parsed.steps if s.program_code == p.code) for p in parsed.programs]
    assert per == [16, 8, 6, 8, 10, 7, 12]
    assert len(parsed.steps) == 67
    assert sum(1 for s in parsed.steps if s.mandatory) == 21
    assert len(parsed.items) == 24  # the PBC template's 24 requests
    assert [p.code for p in parsed.programs][2] == "BH-EBP-210"  # sampling, as the packs cite


def test_ebp_v2_has_64_steps_and_v3_adds_four_and_removes_one() -> None:
    v2 = parse_workbook(workbook(spec_of("ebp", 2)), programs=True)
    assert len(v2.steps) == 64
    assert 67 - 64 == 4 - 1


def test_every_version_is_imported_then_approved_in_order() -> None:
    events = methodology_events()
    imports = [e for e in events if e.kind == "methodology.version_imported"]
    approvals = [e for e in events if e.kind == "methodology.version_approved"]
    assert len(imports) == len(approvals) == len(VERSIONS) == 10
    assert all(i.at < a.at for i, a in zip(imports, approvals, strict=True))
    ebp = [str(e.data["effective_from"]) for e in approvals if e.data["family"] == "ebp"]
    assert ebp == ["2024-01-01", "2025-01-01", "2026-01-01"]


def test_a_rebuilt_workbook_parses_to_the_same_rows() -> None:
    first = parse_workbook(workbook(spec_of("fs", 5)), programs=True)
    again = parse_workbook(workbook(spec_of("fs", 5)), programs=True)
    assert (first.programs, first.steps) == (again.programs, again.steps)
