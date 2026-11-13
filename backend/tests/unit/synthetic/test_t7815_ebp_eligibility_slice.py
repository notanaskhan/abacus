"""TASK-7815 (DEC-4813): the `ebp2` slice's EBP-03 eligibility test on Northwind PY2025.

The figures EBP-03 reads come from the handoff (`apps/web/src/fixtures/seed/ebp03.ts`) and A-05
§2, and code computes the rest: this pins that the census and HR records the slice uploads give,
through the import parser and the eligibility engine, the handoff's entry dates, its two
exceptions' missed amounts and row 22's no-effect hire-date difference, and that every event is
dated after E0 and before EBP-03 a's clock (Sep 24, 10:15 AM). The load runs in the full-stack
nightly's Sep 24 pass (J03 12).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from abacus.modules.assurance.compute.ebp import eligibility
from abacus.modules.assurance.compute.ebp.provisions import PROVISIONS, provisions_for
from abacus.modules.assurance.ebp_imports import census_ties, parse
from abacus.modules.evidence.extraction import extract
from abacus_tools.synthetic.scenarios.brightwater_hale import ebp, ebp2, sampling_content
from abacus_tools.synthetic.scenarios.brightwater_hale import ebp_eligibility as e
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT, DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EBP03_CLOCK = datetime(2026, 9, 24, 10, 15, tzinfo=CT)
# The handoff's entry dates (ebp03.ts), in A-03's draw order.
ENTRY = (
    "2025-06-01", "2021-10-01", "2025-08-01", "2013-01-01", "2025-01-01", "2023-07-01",
    "2025-10-01", "2025-07-01", "2020-02-01", "2025-03-01", "2017-06-01", "2023-12-01",
    "2025-11-01", "2015-09-01", "2025-04-01", "2022-05-01", "2024-11-01", "2023-09-01",
    "2025-09-01", "2018-12-01", "2017-03-01", "2025-02-01", "2021-04-01", "2022-10-01",
    "2025-09-01",
)  # fmt: skip


def _rows(kind: str, content: bytes, column_map: dict[str, str]) -> dict[str, dict[str, object]]:
    table = extract(content, XLSX).tables[0]
    parsed = parse(kind, table, column_map)
    assert parsed.refusal is None
    return {str(r["participant_key"]): dict(r) for r in parsed.rows}


def test_the_census_ties_to_the_w3_and_keeps_audit11s_rows() -> None:
    rows = e.census()
    base = sampling_content.census()
    assert [r.row_key for r in rows] == [r.row_key for r in base]
    assert sum((r.compensation for r in rows), Decimal(0)) == e.W3_BOX1 + e.W3_BOX12D
    assert e.W3_BOX1 == ebp.W3_BOX1 and e.W3_BOX12D == ebp.W3_BOX12D
    parsed = parse("census", extract(e.census_xlsx(), XLSX).tables[0], e.CENSUS_MAP)
    assert parsed.refusal is None and len(parsed.rows) == 412
    assert census_ties(parsed.totals["compensation"], None, e.W3_BOX1, e.W3_BOX12D) is None
    changed = {r.name for r, b in zip(rows, base, strict=True) if r.compensation != b.compensation}
    assert changed == {"Kwame Mensah", "Yuki Mori", base[-1].name}


def test_the_files_give_the_handoffs_entry_dates_and_missed_amounts() -> None:
    census = _rows("census", e.census_xlsx(), e.CENSUS_MAP)
    roster = _rows("hr_roster", e.hr_xlsx(), e.HR_MAP)
    keys = e.sampled_keys()
    assert len(roster) == 25 and set(roster) == set(keys.values())
    for person, expected in zip(e.SAMPLED, ENTRY, strict=True):
        row, hr = census[keys[person.name]], roster[keys[person.name]]
        dob, hire = row["dob"], row["hire_on"]
        assert isinstance(dob, date) and isinstance(hire, date)
        assert eligibility.entry(dob, hire).entry_on == date.fromisoformat(expected)
        assert isinstance(hr["hire_on"], date)
        review = eligibility.review(dob, hire, hr["hire_on"])
        assert review.no_effect is (person.name == "Benjamin Okoro")
    kwame, yuki = census[keys["Kwame Mensah"]], census[keys["Yuki Mori"]]
    assert eligibility.missed(Decimal(str(kwame["compensation"]))).deferral == Decimal("2472.00")
    assert eligibility.missed(Decimal(str(kwame["compensation"]))).match == Decimal("1442.00")
    assert eligibility.missed(Decimal(str(yuki["compensation"]))).deferral == Decimal("3168.00")
    assert eligibility.missed(Decimal(str(yuki["compensation"]))).match == Decimal("1848.00")
    # Fatima: age 21 on Aug 19, 2025 governs, so no eligibility date may be shown (DEC-2225).
    fatima = census[keys["Fatima Qureshi"]]
    entry = eligibility.entry(fatima["dob"], fatima["hire_on"])  # type: ignore[arg-type]  # -- dates, checked above
    assert entry.eligible_on != entry.service_on


def test_the_results_are_two_exceptions_and_one_no_effect() -> None:
    marks = [e.result_of(p, a) for p in e.SAMPLED for a in e.ATTRIBUTES]
    assert len(marks) == 100
    exceptions = [n for n, p in enumerate(e.SAMPLED, 1) if p.result == "exception"]
    assert exceptions == [8, 15]
    assert [n for n, p in enumerate(e.SAMPLED, 1) if p.result == "no_effect"] == [22]
    assert all(note for result, note in marks if result != "pass")
    assert sum(result != "pass" for result, _ in marks) == 3


def test_the_entry_rule_wording_is_one_code_reads() -> None:
    assert [p.key for p in PROVISIONS] == [k for k, _, _ in e.PROVISIONS]
    for amended in (True, False):
        held = e.held_provisions(amended=amended)
        assert [(row, k) for row, (k, _, _) in held] == [
            (p.row, p.key) for p in provisions_for(amendment_in_force=amended)
        ]
    verified = {k: v for k, v, _ in e.PROVISIONS}
    assert eligibility.entry_rule_from(verified) == eligibility.EntryRule(21, 3)


def test_the_events_ride_ebp2_after_e0_and_before_ebp03s_clock() -> None:
    events = [ev for ev in slice_events(ebp2.SLICE) if ev.label.startswith("ebp:northwind:")]
    ours = [ev for ev in events if ev.label != "ebp:northwind:documents:part2"]
    assert [ev.kind for ev in ours] == [
        "engagements.ebp_preparer_assigned",
        "assurance.ebp_plan_review_started",
        "assurance.ebp_provisions_keyed",
        "assurance.ebp_provisions_verified",
        "evidence.ebp_eligibility_files_uploaded",
        "assurance.ebp_import_recorded",
        "assurance.ebp_import_recorded",
        "assurance.ebp_test_created",
        "assurance.ebp_results_marked",
    ]
    assert [ev.actor for ev in ours] == ["HL", "MD", "MD", "HL", "system", "AC", "AC", "AC", "AC"]
    assert all(DEMO_INSTANT < ev.at < EBP03_CLOCK for ev in ours)
    assert [ev.at for ev in ours] == sorted(ev.at for ev in ours)
