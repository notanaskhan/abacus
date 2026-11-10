"""T-03-T15 (TASK-3337; DEC-2371): the slice foots to BND-03 and TAX-13, from the row.

"make seed-demo and make fixtures produce identical data whose counts foot to every BND-03 and
TAX-13 artboard at its clock." The loaded half is `tests/integration/test_t03t15_load.py`.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from abacus_tools.synthetic.scenarios.brightwater_hale import tax_schedules as ts
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_board import BOARD_BY_LABEL


def test_ac_the_organizer_file_is_nine_questions_and_four_follow_ups() -> None:
    rows = list(csv.DictReader(io.StringIO(ts.organizer_csv().decode())))
    follow_ups = [r["key"] for r in rows if r["conditional_on"]]
    assert (len(rows) - len(follow_ups), len(follow_ups)) == (9, 4)


def test_ac_claire_answers_eight_of_nine() -> None:
    assert len(ts.ANSWERS) == 8
    assert "q9" not in ts.ANSWERS


def test_ac_the_extension_tiles_foot() -> None:
    # Likely is 1 of TAX-13 c's 2: Thornbury's 706 has no return to flag (DEC-2371).
    assert ts.counts() == {"extended": 161, "open": 79, "filed": 82, "likely": 1}


def test_ac_the_named_rows_sit_in_open_with_their_figures() -> None:
    open_clients = {
        BOARD_BY_LABEL[label].client
        for index, label in enumerate(ts.extended_rows())
        if ts.state_of(index) == "open"
    }
    assert {line.client for line in ts.LINES} <= open_clients


def test_ac_the_estimate_tiles_foot() -> None:
    """TAX-13 b (DF-34, TASK-3397): Q3 due 5 = Paid 2 + Scheduled 1 + Awaiting confirmation 2
    (Meera Shah's request out, Gloria Mendez's not confirmed); Not required 2; 7 rows."""
    statuses = [e.status for e in ts.ESTIMATES]
    assert len(statuses) == 7
    assert statuses.count("paid") == 2
    assert statuses.count("scheduled") == 1
    assert statuses.count("confirmation_requested") + statuses.count("not_confirmed") == 2
    assert statuses.count("not_required") == 2
    by = {e.client: e for e in ts.ESTIMATES}
    assert [c for c, e in by.items() if e.status == "confirmation_requested"] == ["Meera Shah"]
    assert {c: e.confirmer for c, e in by.items() if e.confirmer} == {
        "Jonah & Claire Feld": "Claire Feld",
        "Calloway Family Trust": "Eleanor Calloway",
        "Elena Varga": "Elena Varga",
    }
    assert "Aurelio Santos" not in by and "Gloria Mendez" in by


def test_ac_every_confirmation_comes_back_before_e0() -> None:
    e0 = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
    for e in ts.ESTIMATES:
        if e.confirmed is not None:
            assert e.requested is not None and e.requested < e.confirmed < e0


def test_ac_the_slice_names_every_event_once() -> None:
    labels = [e.label for e in slice_events(ts.SLICE)]
    assert len(labels) == len(set(labels))
