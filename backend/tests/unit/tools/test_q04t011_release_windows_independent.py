# ac-test-author: ayushkbhatia
"""Q-04-T011 (ADR-078; SPEC-403 AC-13; Q-04 AC-1.x, AC-2.1, AC-2.3, AC-2.5, AC-4.1 to AC-4.4): the
independent suite for the release windows, the release gate, the flip guard and the flip
ops-request check, written from the P-29 note (`docs/ops/release-windows.md` §6) and not from the
code. Every date below is the note's table typed by hand. Each guard has tests that fail when it is
removed: the window start and end at Sep 1 00:00 CT and Oct 20 23:59 CT, every weekday of every
deadline week, every in-window Tuesday slot's edges, the migrate hold, the approver rule, the
rollback rule and the 24-hour journey rule."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import yaml

from abacus_tools import release_windows as rw
from abacus_tools.flip_guard import Flip
from abacus_tools.flip_guard import check as flip_check
from abacus_tools.flip_request import FlipRequest, precheck
from abacus_tools.flip_request import parse as parse_request
from abacus_tools.release import window_gate

CT = ZoneInfo("America/Chicago")
TAX = "00000000-0000-4000-8000-0000000000a1"  # live on EBP work: both windows
AUDIT = "00000000-0000-4000-8000-0000000000a2"  # audit only: season windows

# The note's §6 table, by hand.
WINDOWS = {
    "autumn-2027": (date(2027, 9, 1), date(2027, 10, 20)),
    "season-2028": (date(2028, 1, 1), date(2028, 4, 20)),
    "autumn-2028": (date(2028, 9, 1), date(2028, 10, 20)),
    "season-2029": (date(2029, 1, 1), date(2029, 4, 20)),
    "autumn-2029": (date(2029, 9, 1), date(2029, 10, 20)),
}
DEADLINE_WEEKS = {
    "autumn-2027": [
        (date(2027, 9, 13), date(2027, 9, 17)),
        (date(2027, 9, 27), date(2027, 10, 1)),
        (date(2027, 10, 11), date(2027, 10, 15)),
    ],
    "season-2028": [
        (date(2028, 3, 13), date(2028, 3, 17)),
        (date(2028, 4, 17), date(2028, 4, 21)),
    ],
    "autumn-2028": [
        (date(2028, 9, 11), date(2028, 9, 15)),
        (date(2028, 10, 2), date(2028, 10, 6)),
        (date(2028, 10, 16), date(2028, 10, 20)),
    ],
    "season-2029": [
        (date(2029, 3, 12), date(2029, 3, 16)),
        (date(2029, 4, 16), date(2029, 4, 20)),
    ],
    "autumn-2029": [
        (date(2029, 9, 17), date(2029, 9, 21)),
        (date(2029, 10, 1), date(2029, 10, 5)),
        (date(2029, 10, 15), date(2029, 10, 19)),
    ],
}
MINI_FREEZES = {
    "autumn-2027": [
        (date(2027, 9, 8), date(2027, 9, 15)),
        (date(2027, 9, 23), date(2027, 9, 30)),
        (date(2027, 10, 8), date(2027, 10, 15)),
    ],
    "autumn-2028": [
        (date(2028, 9, 8), date(2028, 9, 15)),
        (date(2028, 9, 25), date(2028, 10, 2)),
        (date(2028, 10, 9), date(2028, 10, 16)),
    ],
    "autumn-2029": [
        (date(2029, 9, 10), date(2029, 9, 17)),
        (date(2029, 9, 24), date(2029, 10, 1)),
        (date(2029, 10, 8), date(2029, 10, 15)),
    ],
}
AUTUMN_SLOTS = {
    "autumn-2027": [date(2027, 9, 7), date(2027, 9, 21), date(2027, 10, 5), date(2027, 10, 19)],
    "autumn-2028": [date(2028, 9, 5), date(2028, 9, 19)],
    "autumn-2029": [date(2029, 9, 4)],
}
SEASON_SKIPPED = {
    "season-2028": [date(2028, 3, 14), date(2028, 4, 18)],
    "season-2029": [date(2029, 3, 13), date(2029, 4, 17)],
}


def ct(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=CT)


@pytest.fixture(scope="module")
def cal() -> rw.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(rw.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {
            "tenant_id": TAX,
            "code": "PF-T1",
            "real_data_since": "2027-06-01",
            "autumn_window": True,
        },
        {
            "tenant_id": AUDIT,
            "code": "PF-A1",
            "real_data_since": "2027-06-01",
            "autumn_window": False,
        },
    ]
    return rw.parse(doc)


def days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


RELEASE: dict[str, object] = {
    "git_sha": "a" * 40,
    "image_digest": "sha256:" + "b" * 64,
    "spa_manifest_sha256": "c" * 64,
    "alembic_head": "0291",
    "openapi_sha256": "d" * 64,
    "infra_sha": "e" * 40,
    "window_mode": "defect_only",
    "rollback": "docs/runbooks/RB-01-deploy-and-rollback.md#rollback",
}
HOTFIX = {
    "hotfix": {"reason": "Production is broken for every firm", "requested_by": "notanaskhan"}
}


# --- the windows: start and end edges (P-29 §1) --------------------------------------------------


@pytest.mark.parametrize("wid", sorted(WINDOWS))
def test_each_window_starts_at_midnight_and_ends_at_23_59_ct(cal: rw.Calendar, wid: str) -> None:
    first, last = WINDOWS[wid]
    firm = TAX
    assert rw.in_window(cal, firm, ct(first, 0, 0)) == wid
    assert rw.in_window(cal, firm, ct(last, 23, 59)) == wid
    assert rw.in_window(cal, firm, ct(first, 0, 0) - timedelta(minutes=1)) is None
    # A deadline week is frozen whole: season 2028's Apr 17-21 runs one day past Apr 20.
    frozen_to = max([last] + [b for _, b in DEADLINE_WEEKS[wid]])
    assert rw.in_window(cal, firm, ct(frozen_to, 23, 59)) == wid
    assert rw.in_window(cal, firm, ct(frozen_to + timedelta(days=1), 0, 0)) is None


def test_season_2028s_deadline_week_is_frozen_past_apr_20(cal: rw.Calendar) -> None:
    fri = ct(date(2028, 4, 21), 19, 30)
    assert rw.in_window(cal, AUDIT, fri) == "season-2028"
    assert "deadline_week_without_hotfix" in window_gate(RELEASE, cal, fri).why


def test_an_audit_only_firm_has_no_autumn_window(cal: rw.Calendar) -> None:
    assert rw.in_window(cal, AUDIT, ct(date(2027, 9, 15), 12)) is None
    assert rw.in_window(cal, AUDIT, ct(date(2028, 1, 1), 0)) == "season-2028"


# --- deadline weeks: no promotion, no flip (P-29 §2) ---------------------------------------------


DEADLINE_DAYS = [
    (wid, d) for wid, weeks in DEADLINE_WEEKS.items() for a, b in weeks for d in days(a, b)
]


@pytest.mark.parametrize(("wid", "day"), DEADLINE_DAYS)
def test_every_deadline_week_day_refuses_promotion_without_a_hotfix(
    cal: rw.Calendar, wid: str, day: date
) -> None:
    at = ct(day, 19, 30)
    refused = window_gate(RELEASE, cal, at)
    assert "deadline_week_without_hotfix" in refused.why, (wid, day)
    assert window_gate({**RELEASE, **HOTFIX}, cal, at).why == ()


@pytest.mark.parametrize(("wid", "day"), DEADLINE_DAYS)
def test_every_deadline_week_day_has_no_flip_slot(cal: rw.Calendar, wid: str, day: date) -> None:
    flip = Flip(
        firm=UUID(TAX),
        operator="ayushkbhatia",
        at=ct(day, 19, 30),
        approved_by="notanaskhan",
        rollback="docs/ops/flips/x.md#rollback",
        request_sha256="f" * 64,
    )
    assert "no_slot" in flip_check(cal, flip).why, (wid, day)


# --- mini-freezes and the Tuesday slot (P-29 §2) -------------------------------------------------


@pytest.mark.parametrize(
    ("wid", "slot"), [(w, d) for w, slots in AUTUMN_SLOTS.items() for d in slots]
)
def test_each_autumn_slot_opens_at_19_00_and_closes_at_21_00(
    cal: rw.Calendar, wid: str, slot: date
) -> None:
    assert rw.flip_slot(cal, ct(slot, 19, 0), TAX) is True, (wid, slot)
    assert rw.flip_slot(cal, ct(slot, 20, 59), TAX) is True
    assert rw.flip_slot(cal, ct(slot, 18, 59), TAX) is False
    assert rw.flip_slot(cal, ct(slot, 21, 0), TAX) is False


@pytest.mark.parametrize("wid", sorted(AUTUMN_SLOTS))
def test_no_other_autumn_tuesday_has_a_slot(cal: rw.Calendar, wid: str) -> None:
    first, last = WINDOWS[wid]
    tuesdays = [d for d in days(first, last) if d.weekday() == 1]
    open_ = [d for d in tuesdays if rw.flip_slot(cal, ct(d, 19, 30), TAX)]
    assert open_ == AUTUMN_SLOTS[wid]


@pytest.mark.parametrize("wid", sorted(MINI_FREEZES))
def test_every_mini_freeze_day_has_no_slot(cal: rw.Calendar, wid: str) -> None:
    for a, b in MINI_FREEZES[wid]:
        for day in days(a, b):
            assert rw.flip_slot(cal, ct(day, 19, 30), TAX) is False, (wid, day)


@pytest.mark.parametrize("wid", sorted(SEASON_SKIPPED))
def test_season_tuesdays_all_have_a_slot_but_the_deadline_weeks(
    cal: rw.Calendar, wid: str
) -> None:
    first, last = WINDOWS[wid]
    closed = [
        d
        for d in days(first, last)
        if d.weekday() == 1 and not rw.flip_slot(cal, ct(d, 19, 30), AUDIT)
    ]
    assert closed == SEASON_SKIPPED[wid]


# --- the release gate (P-29 §2, §4) --------------------------------------------------------------


def test_in_a_window_a_release_names_its_mode_and_rollback(cal: rw.Calendar) -> None:
    slot = ct(date(2027, 9, 21), 19, 5)
    for missing in ("window_mode", "rollback"):
        record = {k: v for k, v in RELEASE.items() if k != missing}
        assert f"{missing}_missing" in window_gate(record, cal, slot).why
    assert window_gate(RELEASE, cal, slot).why == ()


def test_in_a_window_promotion_is_the_tuesday_slot(cal: rw.Calendar) -> None:
    assert window_gate(RELEASE, cal, ct(date(2027, 9, 23), 10)).why == (
        "outside_the_tuesday_slot",
    )
    assert (
        window_gate(RELEASE, cal, ct(date(2027, 11, 4), 10)).why == ()
    )  # outside: Thursday train


def test_in_a_window_migrations_wait_for_8_pm_ct(cal: rw.Calendar) -> None:
    held = window_gate(RELEASE, cal, ct(date(2027, 9, 21), 19, 5)).migrate_not_before
    assert held == ct(date(2027, 9, 21), 20, 0)
    outside = ct(date(2027, 11, 4), 10)
    assert window_gate(RELEASE, cal, outside).migrate_not_before == outside


def test_with_no_live_firm_nothing_is_held() -> None:
    committed = rw.load()
    assert (
        window_gate(
            {k: v for k, v in RELEASE.items() if k not in ("window_mode", "rollback")},
            committed,
            ct(date(2027, 9, 15), 19, 30),
        ).why
        == ()
    )


# --- the flip guard (P-29 §2; DEC-02) ------------------------------------------------------------


def _flip(**over: object) -> Flip:
    fields: dict[str, object] = {
        "operator": "ayushkbhatia",
        "at": ct(date(2027, 9, 21), 19, 10),
        "approved_by": "notanaskhan",
        "rollback": "docs/ops/flips/x.md#rollback",
        "request_sha256": "f" * 64,
        **over,
    }
    return Flip(firm=UUID(TAX), **fields)  # pyright: ignore[reportArgumentType] -- test fields


def test_a_flip_in_the_slot_with_approval_rollback_and_request_is_allowed(
    cal: rw.Calendar,
) -> None:
    assert flip_check(cal, _flip()).why == ()


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"approved_by": "ayushkbhatia"}, "approver_is_operator"),
        ({"approved_by": None}, "approver_missing"),
        ({"rollback": None}, "rollback_missing"),
        ({"request_sha256": None}, "request_missing"),
        ({"at": ct(date(2027, 9, 21), 21, 0)}, "no_slot"),
    ],
)
def test_each_flip_rule_refuses_on_its_own(
    cal: rw.Calendar, over: dict[str, object], reason: str
) -> None:
    assert flip_check(cal, _flip(**over)).why == (reason,)


# --- the flip ops-request check (24-hour journeys) -----------------------------------------------


def _request(tmp: Path) -> FlipRequest:
    raw = {
        "kind": "flag_flip",
        "tenant": TAX,
        "slot": "2027-09-21T19:00:00-05:00",
        "flags": [{"name": "evidence.viewer_v1", "value": "true"}],
        "journeys": ["j04-fs-audit"],
        "shadow_run": "https://example.test/shadow/1",
        "rollback": "docs/ops/flips/2027-09-21-PF-T1.md#rollback",
        "operator": "ayushkbhatia",
        "approved_by": "notanaskhan",
    }
    return parse_request(raw, str(tmp / "flip-2027-09-21-PF-T1.yaml"))


@pytest.mark.parametrize(
    ("hours", "ok"), [(23.99, True), (24.0, True), (24.01, False), (25, False)]
)
def test_a_flip_request_needs_its_journeys_green_within_24_hours(
    cal: rw.Calendar, tmp_path: Path, hours: float, ok: bool
) -> None:
    now = ct(date(2027, 9, 21), 12)
    greens = {"j04-fs-audit": now - timedelta(hours=hours)}
    found = precheck(
        _request(tmp_path), cal, greens, now, {}, {"evidence.viewer_v1": ("true", "false")}
    )
    assert (found == []) is ok, found
