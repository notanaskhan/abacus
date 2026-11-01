"""TASK-2470 (DEC-1530): Brightwater Hale is the synthetic test pilot firm PF-X1.

From the decision, not the code: PF-X1 is listed in the committed release-window calendar as
synthetic with no real-data date, so it is never live and no window ever applies to it (every
platform guard stays inert, DEC-68), while a real-data date on a synthetic firm is refused; the
dossier exists and passes the dossier check; and the `pilot` slice enrols the Feld 2025 return
and Northwind's EBP audit in shadow over a window that covers M11 to M13.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import yaml

from abacus_tools import go_live_dossier
from abacus_tools import release_windows as rw
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS, expand_slices
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import FIRM_ID
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

BRIGHTWATER = UUID("293fc3e7-be13-4767-ae6a-ce245b2dbda9")


def _doc() -> dict[str, Any]:  # Any: the YAML document
    return copy.deepcopy(yaml.safe_load(rw.WINDOWS_FILE.read_text(encoding="utf-8")))


def test_pf_x1_is_brightwater_hale_listed_as_synthetic() -> None:
    assert UUID(FIRM_ID) == BRIGHTWATER
    firm = rw.load().firm("PF-X1")
    assert firm is not None
    assert (firm.tenant_id, firm.synthetic, firm.real_data_since) == (BRIGHTWATER, True, None)
    assert rw.load().firm(BRIGHTWATER) == firm


def test_no_window_ever_applies_to_the_test_firm() -> None:
    cal = rw.load()
    firm = cal.firm("PF-X1")
    assert firm is not None
    day = date(2027, 1, 1)
    while day <= date(2029, 12, 31):
        assert not firm.live_on(day)
        assert not any(w.applies_to(firm, day) for w in cal.windows)
        day += timedelta(days=1)
    # Inside a deadline week the guard is still inert for it.
    at = datetime.fromisoformat("2027-09-14T10:00:00-05:00")
    assert rw.in_window(cal, "PF-X1", at) is None


def test_a_synthetic_firm_with_a_real_data_date_is_refused() -> None:
    doc = _doc()
    doc["firms"][0]["real_data_since"] = "2027-06-01"
    with pytest.raises(rw.WindowsError, match="synthetic firm has no real_data_since"):
        rw.parse(doc)
    doc = _doc()
    doc["firms"][0]["synthetic"] = "yes"
    with pytest.raises(rw.WindowsError, match="synthetic is true or false"):
        rw.parse(doc)


def test_a_real_firm_beside_it_is_still_frozen() -> None:
    doc = _doc()
    real = UUID("00000000-0000-4000-8000-0000000000a1")
    doc["firms"].append(
        {
            "tenant_id": str(real),
            "code": "PF-T1",
            "real_data_since": "2027-06-01",
            "autumn_window": True,
        }
    )
    cal = rw.parse(doc)
    at = datetime.fromisoformat("2027-09-14T10:00:00-05:00")
    assert rw.in_window(cal, "PF-T1", at) is not None
    assert rw.in_window(cal, "PF-X1", at) is None


def test_the_dossier_exists_and_is_marked_as_the_test_firm() -> None:
    assert go_live_dossier.PILOT.fullmatch("PF-X1")
    text = (go_live_dossier.DOSSIERS / "PF-X1.md").read_text(encoding="utf-8")
    assert "synthetic test pilot firm (DEC-1530), not a live firm" in text
    assert go_live_dossier.main(["check", "PF-X1"]) == 0


def test_the_pilot_slice_enrols_feld_and_northwind_in_shadow() -> None:
    assert expand_slices(("pilot",)) == ("binders", "portal", "pilot")
    events = slice_events("pilot")
    assert [(e.data["kind"], e.data["target"]) for e in events] == [
        ("return", "Jonah & Claire Feld"),
        ("audit", "A1"),  # Northwind Robotics' PY2025 EBP audit
    ]
    for e in events:
        assert e.kind == "platform.pilot_enrolled" and e.kind in HANDLERS
        assert e.actor == "system"
        assert (e.data["window_start"], e.data["window_end"]) == ("2026-09-01", "2027-10-20")
        assert e.data["baseline_days"] == 14
        assert "mode" not in e.data  # moving a mode stays the operator's
    # The window covers M11 (Aug 17, 2027) to M13 (Aug 31, 2027).
    assert date(2026, 9, 1) <= date(2027, 8, 17) <= date(2027, 8, 31) <= date(2027, 10, 20)
