"""A-07-T12 (TASK-3316; DEC-2315): template content part 1, from the row.

"make seed-demo loads every template through the import endpoints, the licensed-text detector
reports
zero hits, and no template wording appears in Python or TypeScript sources." Counts from the row:
EQR 10, EBP completion 18, archive 9, the representation letter's 11 locked and 4 triggered.
"""

from __future__ import annotations

from pathlib import Path

from abacus.modules.reporting.contract import TemplateImportIn
from abacus.modules.reporting.templates import validate
from abacus_tools.synthetic.scenarios.brightwater_hale import report_templates as rt
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

CONTENT = rt.a07_content()
REPO = Path(__file__).resolve().parents[4]


def test_ac_the_checklists_have_the_rows_counts() -> None:
    assert len(CONTENT["eqr_checklist"]) == 10
    assert len(CONTENT["completion_ebp"]) == 18
    assert len(CONTENT["archive_checklist"]) == 9
    assert [i["key"] for i in CONTENT["archive_checklist"] if i.get("type_specific")] == [
        "filing_type_item"
    ]


def test_ac_the_rep_letter_has_eleven_locked_and_four_triggered() -> None:
    letter = next(b for b in CONTENT["bundles"] if b["family"] == "representation_letter")
    assert len(letter["paragraphs"]["general"]) == 11
    specific = letter["paragraphs"]["specific"]
    assert [p["no"] for p in specific] == [12, 13, 14, 15]
    assert all(p["trigger"] for p in specific)


def test_ac_every_bundle_passes_the_import_validation() -> None:
    for raw in CONTENT["bundles"]:
        body = TemplateImportIn.model_validate(rt.bundle(raw["name"]))
        problems, _ = validate(body)
        assert not problems, (raw["name"], problems)


def test_ac_the_slice_imports_and_publishes_each_letter() -> None:
    events = slice_events(rt.A07_SLICE)
    kinds = [e.kind for e in events]
    assert kinds.count("reporting.template_imported") == len(CONTENT["bundles"])
    assert kinds.count("reporting.template_published") == len(CONTENT["bundles"])


def test_ac_no_template_wording_in_python_or_typescript_sources() -> None:
    phrase = "fair presentation of the financial statements"
    for root in ("backend/src/abacus", "apps/web/src", "packages"):
        for path in (REPO / root).rglob("*"):
            if path.suffix in (".py", ".ts", ".tsx") and "node_modules" not in path.parts:
                assert phrase not in path.read_text(errors="ignore"), path
