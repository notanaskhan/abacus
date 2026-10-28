"""Q-04-T003 (SPEC-403 AC-5 to AC-7; Q-04 AC-2.1, AC-2.3, AC-2.5; P-29): the release window gate.
On a simulated in-window date a release without `window_mode` or a rollback link is refused; a
deadline-week release passes only with `hotfix` and a reason; promotion is the Tuesday slot; the
migrate step waits for 20:00 CT; outside every window nothing is required. The workflow calls the
gate before the lock and holds the migrate step on its answer."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus_tools import release, release_windows
from abacus_tools.release import Refused, check, window_gate

REPO = Path(__file__).resolve().parents[4]
CT = release_windows.CT
GOOD: dict[str, object] = {
    "git_sha": "a" * 40,
    "image_digest": "sha256:" + "b" * 64,
    "spa_manifest_sha256": "c" * 64,
    "alembic_head": "0291",
    "openapi_sha256": "d" * 64,
    "infra_sha": "e" * 40,
}
IN_WINDOW = {
    "window_mode": "defect_only",
    "rollback": "docs/runbooks/RB-01-deploy-and-rollback.md#rollback",
}
HOTFIX = {
    "hotfix": {"reason": "Portal sign-in fails for every client", "requested_by": "notanaskhan"}
}


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=CT)


def calendar(live: bool = True) -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {
            "tenant_id": "00000000-0000-4000-8000-0000000000a1",
            "code": "PF-A1",
            "real_data_since": "2027-06-01" if live else None,
            "autumn_window": True,
        }
    ]
    return release_windows.parse(doc)


def gate(rel: Mapping[str, object], when: str, live: bool = True) -> release.WindowVerdict:
    return window_gate({**GOOD, **rel}, calendar(live), at(when))


SLOT = "2027-09-21 19:05"  # Tue, in the autumn-2027 slot, no deadline week


def test_ac5_in_a_window_a_release_without_window_mode_or_rollback_is_refused() -> None:
    assert gate({}, SLOT).why == ("window_mode_missing", "rollback_missing")
    assert gate({"window_mode": "dark_only"}, SLOT).why == ("rollback_missing",)
    passed = gate(IN_WINDOW, SLOT)
    assert passed.why == ()
    assert passed.window == "autumn-2027"


def test_ac5_outside_every_window_nothing_is_required() -> None:
    outside = gate({}, "2027-11-04 10:00")  # the Thursday train
    assert (outside.why, outside.window) == ((), None)
    assert outside.migrate_not_before == at("2027-11-04 10:00")


def test_ac5_with_no_live_firm_the_gate_is_inert() -> None:
    assert gate({}, SLOT, live=False).why == ()


def test_promotion_inside_a_window_is_the_tuesday_slot_only() -> None:
    assert gate(IN_WINDOW, "2027-09-23 10:00").why == ("outside_the_tuesday_slot",)  # Thu
    assert gate(IN_WINDOW, "2027-09-21 21:00").why == ("outside_the_tuesday_slot",)
    assert gate({**IN_WINDOW, **HOTFIX}, "2027-09-23 10:00").why == ()


@pytest.mark.parametrize("when", ["2027-09-15 19:30", "2027-09-14 19:30", "2027-10-12 19:30"])
def test_ac6_a_deadline_week_release_passes_only_with_a_hotfix_and_a_reason(when: str) -> None:
    refused = gate(IN_WINDOW, when)
    assert refused.why == ("deadline_week_without_hotfix",)
    assert refused.deadline_week is not None
    passed = gate({**IN_WINDOW, **HOTFIX}, when)
    assert passed.why == ()
    assert json.loads(passed.as_json())["in_window_hotfix"] is True


@pytest.mark.parametrize(
    "hotfix",
    [
        {"reason": "short", "requested_by": "notanaskhan"},
        {"reason": "Portal sign-in fails for every client"},
        {"reason": "Portal sign-in fails for every client", "requested_by": "Not A Handle"},
        {"reason": "Portal sign-in fails", "requested_by": "notanaskhan", "extra": 1},
        "now please",
    ],
)
def test_ac6_a_hotfix_without_a_reason_and_a_handle_is_refused(hotfix: object) -> None:
    with pytest.raises(Refused, match="hotfix"):
        check({**GOOD, "hotfix": hotfix}, production=True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("window_mode", "whenever"),
        ("rollback", "see slack"),
        ("rollback", "http://example.test/rollback"),
        ("rollback", "../etc/passwd"),
    ],
)
def test_window_fields_have_their_forms(field: str, value: object) -> None:
    with pytest.raises(Refused, match=field):
        check({**GOOD, field: value}, production=True)
    with pytest.raises(Refused, match="release keys"):
        check({**GOOD, "window_mode": "dark_only"})  # a staging record never carries them


def test_ac7_the_migrate_step_waits_for_8_pm_ct_inside_a_window() -> None:
    assert gate(IN_WINDOW, SLOT).migrate_not_before == at("2027-09-21 20:00")
    assert gate(IN_WINDOW, "2027-09-21 20:10").migrate_not_before == at("2027-09-21 20:10")


def test_the_cli_answers_json_and_refuses_with_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rel = tmp_path / "release.json"
    rel.write_text(json.dumps(GOOD))

    def load(_path: Path) -> release_windows.Calendar:
        return calendar()

    monkeypatch.setattr(release_windows, "load", load)
    assert (
        release.main(["window-gate", "--release", str(rel), "--at", "2027-09-21T19:05:00-05:00"])
        == 1
    )
    out = json.loads(capsys.readouterr().out)
    assert out["refused"] == ["window_mode_missing", "rollback_missing"]
    rel.write_text(json.dumps({**GOOD, **IN_WINDOW}))
    assert (
        release.main(["window-gate", "--release", str(rel), "--at", "2027-09-21T19:05:00-05:00"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["migrate_not_before"] == "2027-09-21T20:00:00-05:00"
    assert release.main(["window-gate", "--release", str(rel), "--at", "2027-09-21T19:05:00"]) == 1


def test_the_placeholder_passes_the_window_gate(capsys: pytest.CaptureFixture[str]) -> None:
    placeholder = REPO / "deploy/production/release.json"
    assert release.main(["window-gate", "--release", str(placeholder)]) == 0
    assert capsys.readouterr().out.strip() == "placeholder"


def test_the_committed_calendar_lists_no_live_firm_so_production_is_not_held() -> None:
    verdict = window_gate(GOOD, release_windows.load(), at("2027-09-15 19:30"))
    assert verdict.why == ()


def _steps() -> list[Mapping[str, object]]:
    workflow = cast(
        Mapping[str, object],
        yaml.safe_load((REPO / ".github/workflows/deploy-production.yml").read_text()),
    )
    jobs = cast(Mapping[str, Mapping[str, object]], workflow["jobs"])
    return cast(list[Mapping[str, object]], jobs["deploy"]["steps"])


def test_the_workflow_gates_then_holds_the_migrate_step() -> None:
    steps = _steps()
    names = [str(s.get("name", "")) for s in steps]
    gates = str(steps[names.index("Gates")]["run"])
    assert "abacus_tools.release window-gate" in gates
    assert "migrate_not_before" in gates
    hold = names.index("Hold the migrate step for the window")
    assert (
        names.index("Gates") < names.index("Take the deploy lock") < hold < names.index("Migrate")
    )
    held = str(steps[hold]["run"])
    assert "sleep" in held and "4500" in held
