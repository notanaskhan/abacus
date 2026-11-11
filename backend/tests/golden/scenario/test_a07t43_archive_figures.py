"""A-07-T43 (TASK-6736; ADR-078, author notanaskhan): the issuance-to-archive golden figures
against ayushkbhatia's content, projector and scenario.

Row acceptance: "Every figure above holds on make seed-demo and the tests fail on a one-day or
one-row drift." The figure book (`brightwater_hale/archive_figures.json`) is transcribed from
A-07 §1, F2, F3, F6 and F7; this file holds the firm content (`a07_templates.yaml`), the code's
clocks and the `archive` slice to it, `tests/integration/test_a07t43_archive_golden.py` holds
the loaded tenant to it, and `apps/web/src/fixtures/contracts/archive-figures.test.ts` the
screens' fixtures.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import completion_projector as projector
from abacus.modules.assurance import rep_letters
from abacus.modules.assurance.archive_gate import ARCHIVE_ITEMS
from abacus.modules.assurance.archive_records import five_year_floor
from abacus.modules.assurance.release import DOCUMENTATION_DAYS, ReleasedFacts
from abacus_tools.synthetic.scenarios.brightwater_hale import archive_slice as archive
from abacus_tools.synthetic.scenarios.brightwater_hale import completion_slice as completion
from abacus_tools.synthetic.scenarios.brightwater_hale.compliance import POLICIES
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import a07_content
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

HERE: Final = Path(__file__).resolve().parent
BOOK: Final = cast(
    dict[str, dict[str, Any]],  # Any: JSON
    json.loads((HERE / "brightwater_hale" / "archive_figures.json").read_text(encoding="utf-8")),
)
CONTENT: Final = a07_content()


def _event(label: str) -> datetime:
    return next(e.at for e in slice_events(archive.SLICE) if e.label == label)


def _released(at: datetime) -> ReleasedFacts:
    return ReleasedFacts(uuid.uuid4(), uuid.uuid4(), at, at.date(), (), None, uuid.uuid4())


# --- the clocks: Oct 9 + 60 = Dec 8; Archive in 47 days on Oct 22 -----------------------------


def test_ac_oct_9_plus_60_is_dec_8_from_the_scenarios_release() -> None:
    book = BOOK["release"]
    at = _event("archive:A1:release")
    assert at == datetime.fromisoformat(book["at"])
    assert book["documentation_days"] == DOCUMENTATION_DAYS
    assert _released(at).documentation_completion_date == date.fromisoformat(
        book["documentation_completion_date"]
    )


def test_a_one_day_drift_in_the_release_moves_the_date() -> None:
    at = _event("archive:A1:release")
    later = _released(at + timedelta(days=1)).documentation_completion_date
    assert later != date.fromisoformat(BOOK["release"]["documentation_completion_date"])


def test_a_late_evening_release_counts_from_the_firms_date_not_utc() -> None:
    """10:30 PM CDT on Oct 9 is Oct 10 in UTC: the AU-C 230 clock reads the firm's date."""
    late = datetime.fromisoformat("2026-10-09T22:30:00-05:00")
    assert _released(late).documentation_completion_date.isoformat() == "2026-12-08"


def test_ac_archive_in_47_days_on_oct_22() -> None:
    book = BOOK["assembling"]
    due = date.fromisoformat(BOOK["release"]["documentation_completion_date"])
    on = snapshot("2026-10-22T09:30").at.date()
    assert on.isoformat() == book["on"]
    assert (due - on).days == book["days_left"]  # archive_gate.archive_state's days_left
    assert DOCUMENTATION_DAYS - book["days_left"] == book["days_elapsed"]


def test_the_lock_is_dec_3_at_4_18_pm_cst_five_days_before_the_deadline() -> None:
    book = BOOK["lock"]
    at = _event("archive:A1:locked")
    assert at == datetime.fromisoformat(book["at"])
    due = date.fromisoformat(BOOK["release"]["documentation_completion_date"])
    assert (due - at.date()).days == book["days_left"]


def test_ac_retention_to_oct_9_2033_and_the_records_floor_to_2031() -> None:
    book = BOOK["retention"]
    release = date.fromisoformat(BOOK["release"]["date"])
    policy = next(p for p in POLICIES if p.record_type == "audit_documentation")
    assert int(policy.firm_years) == book["firm_years"]
    assert policy.clock_start_event == "report_release"
    firm = release.replace(year=release.year + int(policy.firm_years))
    assert firm.isoformat() == book["retention_until"]
    assert five_year_floor(release).isoformat() == book["records_until"]
    assert max(firm, five_year_floor(release)).isoformat() == book["retention_until"]


# --- the checklists: 6 of 10; 12 of 17; 8 of 9 ------------------------------------------------


def test_ac_the_eqr_checklist_is_ten_items_and_six_are_done_by_11_05() -> None:
    book = BOOK["eqr_checklist"]
    assert len(CONTENT["eqr_checklist"]) == book["total"] == archive.EQR_ITEMS
    first = next(e for e in slice_events(archive.SLICE) if e.label == "archive:A1:eqr-items-1")
    assert first.data["done"] == book["done_at_1105"]
    assert first.at < snapshot("2026-10-05T11:05").at
    assert len(archive.EQR_NOTES) == book["notes"]


def test_ac_the_completion_checklist_is_12_of_17_with_its_tags() -> None:
    """AUD-19 a: 18 rows, 12 done, 1 not applicable, 5 open; the summary excludes N/A; two
    client-dependent and two due on the report date."""
    book = BOOK["completion_checklist"]
    rows = CONTENT["completion_ebp"]
    assert len(rows) == book["rows"] == book["done"] + book["not_applicable"] + book["open"]
    assert book["summary_total"] == book["rows"] - book["not_applicable"]
    assert sum(bool(r.get("depends_on_client")) for r in rows) == book["client_dependent"]
    assert sum(bool(r.get("due_on_report_date")) for r in rows) == book["due_on_report_date"]
    assert [r["key"] for r in rows if r.get("gate_tag") == "G7"] == ["rep_letter"]


def test_ac_the_archive_checklist_is_nine_items() -> None:
    book = BOOK["archive_checklist"]
    assert len(ARCHIVE_ITEMS) == book["total"]
    assert book["done_on_oct_22"] == book["total"] - 1


# --- the binder and the SUM on the letter's attachment -----------------------------------------


def test_ac_26_workpapers_in_sections_a_to_e() -> None:
    book = BOOK["binder"]
    rows = completion.MATRIX_ROWS
    planning, fieldwork_testing, done, reporting = (
        len(rows[g]) for g in ("planning", "fieldwork", "completion", "reporting")
    )
    a, b, c, d, e = book["sections"]
    assert [planning, fieldwork_testing, done, reporting] == [a, b + c, d, e]
    assert sum(book["sections"]) == book["workpapers"]
    assert len({ref for refs in rows.values() for ref in refs}) == book["workpapers"]


def _usd(value: object) -> Decimal:
    return Decimal(str(value))


def test_ac_sum_34_150_is_18_1_percent_of_189_150_on_the_attachment() -> None:
    book = BOOK["sum_attachment"]
    passed = [e.finding for e in completion.ENTRIES if e.decision == "client_declined"]
    effects = {f.ref: f.effect for f in completion.FINDINGS}
    rollover = sum(_usd(effects[r]["change_in_net_assets"]) for r in passed)
    iron = sum(_usd(effects[r]["net_assets"]) for r in passed)
    assert rollover == _usd(book["rollover"])
    assert iron == _usd(book["iron_curtain"])
    pct = (rollover / _usd(book["pm"]) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    assert pct == _usd(book["pct_of_pm"])
    assert _usd(book["paje_1"]) + _usd(book["paje_2"]) == _usd(book["iron_curtain"])


# --- DF-27: the letter's paragraph mapping; template variables ---------------------------------


def _bundle(family: str) -> dict[str, Any]:  # Any: YAML
    found = [b for b in CONTENT["bundles"] if b["family"] == family]
    assert len(found) == 1, family
    return found[0]


def test_ac_df27_general_1_to_11_and_specific_12_to_15_by_trigger() -> None:
    book = BOOK["rep_letter"]
    letter = _bundle("representation_letter")["paragraphs"]
    assert len(letter["general"]) == book["general"] == rep_letters.GENERAL
    specific = letter["specific"]
    assert [s["n"] for s in specific] == book["specific"]
    assert {str(s["n"]): s["trigger"] for s in specific} == book["triggers"]
    rep_letters.register_rep_triggers()
    assert {s["trigger"] for s in specific} <= set(rep_letters._TRIGGERS)  # pyright: ignore[reportPrivateUsage]
    assert sorted(book["northwind_on"] + book["northwind_off"]) == book["specific"]


_VAR: Final = re.compile(r"\{\{\s*([a-z_.]+)\s*\}\}")


def test_ac_every_a07_templates_variables_resolve() -> None:
    """The A-07 kinds' providers declare no variables (`a07_registrations._live_variables`), so
    an A-07 bundle that used one would refuse to render (`missing_variable`): none does."""
    for bundle in CONTENT["bundles"]:
        text = json.dumps(bundle)
        assert not _VAR.findall(text), bundle["name"]
        assert '"var"' not in text, bundle["name"]
        assert not bundle.get("variables"), bundle["name"]


# --- T22's projector inert -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flag", "mode", "live"),
    [(True, "in_app", True), (True, "external", False), (False, "in_app", False),
     (False, "external", False)],
)  # fmt: skip
async def test_ac_the_projector_is_inert_for_an_external_firm_and_with_the_flag_off(
    monkeypatch: pytest.MonkeyPatch, flag: bool, mode: str, live: bool
) -> None:
    from abacus.modules.assurance import a07_registrations

    async def flagged(*_: object) -> bool:
        return flag

    async def release_mode(*_: object) -> str:
        return mode

    monkeypatch.setattr(a07_registrations, "live", flagged)
    monkeypatch.setattr(projector, "release_mode", release_mode)
    tenant = TenantContext(uuid.uuid4(), "system", "a07t43")
    assert await projector.projector_live(tenant) is live
