"""Q-04-T004 (SPEC-403 AC-8; Q-04 AC-4.1 to AC-4.5; P-29 rule 3; DEC-02): the flip guard. For a
pilot firm inside its window a flip outside the Tuesday slot, in a deadline week or mini-freeze,
approved by its own operator, or without a rollback link is refused; outside the window only the
approval and rollback rules hold; a firm that is not a pilot firm keeps today's rules."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import yaml

from abacus_tools import flip_guard, release_windows
from abacus_tools.flip_guard import Flip, check, fingerprint

CT = release_windows.CT
A1 = UUID("00000000-0000-4000-8000-0000000000a1")  # PF-A1: EBP, autumn window
A2 = UUID("00000000-0000-4000-8000-0000000000a2")  # PF-A2: audit only
ROLLBACK = "docs/ops/flips/2027-09-21-PF-A1.md#rollback"


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=CT)


@pytest.fixture
def cal() -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {
            "tenant_id": str(A1),
            "code": "PF-A1",
            "real_data_since": "2027-06-01",
            "autumn_window": True,
        },
        {"tenant_id": str(A2), "code": "PF-A2", "real_data_since": "2027-06-01"},
    ]
    return release_windows.parse(doc)


@pytest.fixture
def request_file(tmp_path: Path) -> Path:
    path = tmp_path / "flip-2027-09-21-PF-A1.yaml"
    path.write_text("kind: flag_flip\ntenant: PF-A1\n", encoding="utf-8")
    return path


def flip(when: str, firm: UUID = A1, **over: object) -> Flip:
    fields: dict[str, Any] = {  # Any: Flip's fields
        "firm": firm,
        "operator": "ayushkbhatia",
        "at": at(when),
        "flags": ("sampling.sample_sets",),
        "approved_by": "notanaskhan",
        "rollback": ROLLBACK,
    }
    return Flip(**{**fields, **over})  # pyright: ignore[reportArgumentType] -- test overrides


def test_ac8_an_in_window_flip_in_the_slot_with_approval_rollback_and_request_is_allowed(
    cal: release_windows.Calendar, request_file: Path
) -> None:
    verdict = check(cal, flip("2027-09-21 19:10", request=request_file))
    assert verdict.why == ()
    assert verdict.window == "autumn-2027"
    assert verdict.refs["approved_by"] == fingerprint("notanaskhan")
    assert verdict.refs["rollback"] == fingerprint(ROLLBACK)
    assert verdict.refs["request"] == fingerprint(request_file.read_text())
    assert verdict.refs["slot"] == int(at("2027-09-21 19:00").timestamp())


@pytest.mark.parametrize(
    "when",
    [
        "2027-09-21 18:59",  # before the slot
        "2027-09-21 21:00",  # after it
        "2027-09-23 19:30",  # a Thursday
        "2027-09-14 19:30",  # Tue in a mini-freeze and deadline week (AC-4.2)
        "2027-09-28 19:30",  # Tue in a deadline week
        "2027-10-12 19:30",  # Tue in a mini-freeze and deadline week
    ],
)
def test_ac8_outside_the_slot_or_in_a_freeze_there_is_no_slot(
    cal: release_windows.Calendar, request_file: Path, when: str
) -> None:
    assert check(cal, flip(when, request=request_file)).why == ("no_slot",)


def test_ac8_a_hotfix_with_a_reason_may_flip_outside_the_slot(
    cal: release_windows.Calendar, request_file: Path
) -> None:
    verdict = check(
        cal, flip("2027-09-14 22:00", request=request_file, hotfix="Portal uploads fail for PF-A1")
    )
    assert verdict.why == ()
    assert verdict.refs["hotfix"] == 1
    assert check(cal, flip("2027-09-14 22:00", request=request_file, hotfix="now")).why == (
        "hotfix_reason_missing",
    )


def test_ac8_the_operator_never_approves_their_own_flip(
    cal: release_windows.Calendar, request_file: Path
) -> None:
    verdict = check(
        cal, flip("2027-09-21 19:10", request=request_file, approved_by="ayushkbhatia")
    )
    assert verdict.why == ("approver_is_operator",)
    assert check(cal, flip("2027-09-21 19:10", request=request_file, approved_by=None)).why == (
        "approver_missing",
    )


@pytest.mark.parametrize("rollback", [None, "see the channel", "http://example.test/r"])
def test_ac8_a_flip_names_its_rollback(
    cal: release_windows.Calendar, request_file: Path, rollback: str | None
) -> None:
    verdict = check(cal, flip("2027-09-21 19:10", request=request_file, rollback=rollback))
    assert verdict.why == ("rollback_missing",)


def test_ac8_in_window_a_flip_runs_from_its_ops_request(cal: release_windows.Calendar) -> None:
    assert check(cal, flip("2027-09-21 19:10")).why == ("request_missing",)
    missing = Path("/nonexistent/flip.yaml")
    assert "request_unreadable" in check(cal, flip("2027-09-21 19:10", request=missing)).why


def test_ac8_outside_its_window_only_approval_and_rollback_hold(
    cal: release_windows.Calendar,
) -> None:
    # The audit-only firm in September 2027 (AC-4.4): any day, no slot, no request needed.
    assert check(cal, flip("2027-09-16 10:00", firm=A2)).why == ()
    assert check(cal, flip("2027-09-16 10:00", firm=A2, approved_by=None)).why == (
        "approver_missing",
    )
    assert check(cal, flip("2027-11-04 10:00")).window is None


def test_a_prompt_variant_in_window_needs_the_eval_report_and_shadow_run(
    cal: release_windows.Calendar, request_file: Path
) -> None:
    prompt = flip("2027-09-21 19:10", request=request_file, flags=("prompt.screening",))
    assert check(cal, prompt).why == ("prompt_needs_eval_report_and_shadow_run",)
    full = flip(
        "2027-09-21 19:10",
        request=request_file,
        flags=("prompt.screening",),
        eval_report="docs/quality/evals/screening@v7.md",
        shadow_run="https://example.test/shadow/123",
    )
    verdict = check(cal, full)
    assert verdict.why == ()
    assert {"eval_report", "shadow_run"} <= set(verdict.refs)


def test_a_firm_that_is_not_a_pilot_firm_keeps_todays_rules(
    cal: release_windows.Calendar,
) -> None:
    verdict = check(cal, flip("2027-09-14 22:00", firm=uuid4(), approved_by=None, rollback=None))
    assert (verdict.why, verdict.pilot) == ((), False)


def test_with_no_live_firm_a_pilot_firm_still_names_approver_and_rollback(
    cal: release_windows.Calendar,
) -> None:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [{"tenant_id": str(A1), "code": "PF-A1", "real_data_since": None}]
    early = release_windows.parse(doc)
    assert check(early, flip("2027-09-14 22:00")).why == ()  # no window before real data
    assert check(early, flip("2027-09-14 22:00", approved_by=None)).why == ("approver_missing",)


def test_next_slot_points_at_the_next_allowed_tuesday(cal: release_windows.Calendar) -> None:
    assert flip_guard.next_slot(cal, A1, at("2027-09-13 09:00")) == at("2027-09-21 19:00")
    assert flip_guard.next_slot(cal, A1, at("2027-10-20 09:00")) is None  # the window ends
