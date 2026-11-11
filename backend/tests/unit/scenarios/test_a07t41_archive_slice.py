"""A-07-T41 (TASK-6735; DEC-3302): the `archive` slice's timeline is the design's, every event
has a loader handler, and the slice brings what it needs. The load itself is
`tests/integration/test_a07t41_archive_loaded.py`."""

from __future__ import annotations

from datetime import datetime

from abacus_tools.synthetic.scenarios.brightwater_hale import archive_slice as archive
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS, expand_slices
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered, slice_events


def _at(label: str) -> datetime:
    found = [e for e in slice_events(archive.SLICE) if e.label == label]
    assert len(found) == 1, label
    return found[0].at


def test_the_slice_is_registered_and_every_kind_has_a_handler() -> None:
    assert archive.SLICE in registered()
    kinds = {e.kind for e in slice_events(archive.SLICE)}
    assert kinds - HANDLERS.keys() == set()


def test_the_slice_brings_completion_the_templates_and_the_room_first() -> None:
    order = expand_slices((archive.SLICE,))
    assert order[-1] == archive.SLICE
    for needed in ("completion", "a07_templates", "report_templates", "governance_room"):
        assert order.index(needed) < order.index(archive.SLICE)


def test_northwinds_instants_are_the_designs() -> None:
    assert _at("archive:A1:eqr-concur") == datetime(2026, 10, 5, 16, 40, tzinfo=CT)
    assert _at("archive:A1:letter-v1") == datetime(2026, 10, 2, 8, 20, tzinfo=CT)
    assert _at("archive:A1:letter-approved") == datetime(2026, 10, 5, 17, 10, tzinfo=CT)
    assert _at("archive:A1:report-approved") == datetime(2026, 10, 7, 16, 20, tzinfo=CT)
    assert _at("archive:A1:bring-down") == datetime(2026, 10, 9, 9, 4, tzinfo=CT)
    assert _at("archive:A1:letter-signed") == datetime(2026, 10, 9, 9, 12, tzinfo=CT)
    assert _at("archive:A1:release") == datetime(2026, 10, 9, 10, 7, tzinfo=CT)
    assert _at("archive:A1:letter-265-sent").date().isoformat() == "2026-11-20"
    assert _at("archive:A1:letter-265-ack").date().isoformat() == "2026-11-24"
    locked = _at("archive:A1:locked")
    assert locked == datetime(2026, 12, 3, 16, 18, tzinfo=CT)
    assert locked.utcoffset() is not None and locked.utcoffset().total_seconds() == -6 * 3600
    assert _at("archive:A1:addition-approved").date().isoformat() == "2027-01-15"


def test_granite_peak_and_lakeshore() -> None:
    assert _at("archive:A2:going-concern-decided").date().isoformat() == "2026-10-26"
    assert _at("archive:A2:release").date().isoformat() == "2026-10-27"
    lakeshore = [e for e in slice_events(archive.SLICE) if e.client == archive.LAKESHORE]
    assert [e.at.date().isoformat() for e in lakeshore] == ["2026-11-10"]


def test_the_eqr_checklist_is_six_of_ten_before_11_05_and_ten_after_the_discussion() -> None:
    by_label = {e.label: e for e in slice_events(archive.SLICE)}
    first = by_label["archive:A1:eqr-items-1"]
    assert first.data["done"] == 6 and first.at < datetime(2026, 10, 5, 11, 5, tzinfo=CT)
    second = by_label["archive:A1:eqr-items-2"]
    assert second.data["done"] == 10 and second.at > datetime(2026, 10, 5, 15, 30, tzinfo=CT)


def test_every_act_is_a_named_person_s_except_the_providers_and_the_flags() -> None:
    for event in slice_events(archive.SLICE):
        if event.actor == "system":
            assert event.kind in (
                "platform.flag_set",
                "archive.letter_signed",
                "archive.governance_acknowledged",
            ), event.label
    final = {
        "archive.eqr_concurred": archive.EQR,
        "archive.letter_approved": archive.PARTNER,
        "archive.released": archive.PARTNER,
        "archive.governance_sent": archive.PARTNER,
        "archive.addition_decided": archive.PARTNER,
        "archive.going_concern_decided": archive.PARTNER,
        "archive.locked": archive.MANAGER,
    }
    for event in slice_events(archive.SLICE):
        if event.kind in final:
            assert event.actor == final[event.kind], event.label
