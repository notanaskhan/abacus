"""Q-04-T010 (SPEC-403 AC-12; Q-04 AC-4.1; P-29 rule 3; DEC-809): the flip ops-request check. A
flip request whose journey last passed on staging 25 hours ago, or that names no shadow run,
fails `flip-precheck` and cannot be approved; so does one approved by its operator, for a firm
that is not a pilot firm, or for a slot the firm may not flip in. Merged, it becomes the flag
CLI's command with the request's fingerprint."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus_tools import flip_request, release, release_windows
from abacus_tools.flip_guard import Flip, check
from abacus_tools.flip_request import RequestError, parse, precheck

REPO = Path(__file__).resolve().parents[4]
A1 = "00000000-0000-4000-8000-0000000000a1"
FLAG = "evidence.viewer_v1"  # a registered boolean
NOW = datetime.fromisoformat("2027-09-21T12:00:00-05:00")
FILE = "flip-2027-09-21-PF-A1.yaml"
VALUES: Mapping[str, tuple[str, ...]] = {FLAG: ("true", "false"), "prompt.screening": ("v6", "v7")}


def calendar() -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {"tenant_id": A1, "code": "PF-A1", "real_data_since": "2027-06-01", "autumn_window": True}
    ]
    return release_windows.parse(doc)


def raw(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "flag_flip",
        "tenant": A1,
        "slot": "2027-09-21T19:00:00-05:00",
        "flags": [{"name": FLAG, "value": "true"}],
        "journeys": ["j04-fs-audit"],
        "shadow_run": "https://example.test/shadow/123",
        "rollback": "docs/ops/flips/2027-09-21-PF-A1.md#rollback",
        "operator": "ayushkbhatia",
        "approved_by": "notanaskhan",
    }
    return {**base, **over}


def green(hours_ago: float) -> dict[str, datetime]:
    return {"j04-fs-audit": NOW - timedelta(hours=hours_ago)}


def why(
    request: dict[str, object],
    greens: Mapping[str, datetime],
    file: str = FILE,
    now: datetime = NOW,
    registry: Mapping[str, tuple[str, ...]] | None = None,
) -> list[str]:
    return precheck(parse(request, file), calendar(), greens, now, registry or {}, VALUES)


def test_ac12_a_request_with_fresh_journeys_in_the_slot_is_ready() -> None:
    assert why(raw(), green(3)) == []


def test_ac12_a_journey_that_last_passed_25_hours_ago_fails() -> None:
    assert why(raw(), green(25)) == ["journey_stale:j04-fs-audit"]
    assert why(raw(), green(23.9)) == []
    assert why(raw(), {}) == ["journey_never_green:j04-fs-audit"]


def test_ac12_the_whole_staging_job_counts_for_every_journey() -> None:
    assert why(raw(), {"*": NOW - timedelta(hours=2)}) == []
    assert why(raw(), {"*": NOW - timedelta(hours=30)}) == ["journey_stale:j04-fs-audit"]


def test_ac12_a_request_that_names_no_shadow_run_is_refused() -> None:
    request = raw()
    del request["shadow_run"]
    with pytest.raises(RequestError, match="shadow_run"):
        parse(request, FILE)
    with pytest.raises(RequestError, match="shadow_run"):
        parse(raw(shadow_run="see the doc"), FILE)


def test_ac12_the_operator_never_approves_their_own_flip() -> None:
    assert why(raw(approved_by="ayushkbhatia"), green(1)) == ["approver_is_operator"]


def test_ac12_the_registry_journeys_for_the_flag_are_required_too() -> None:
    registry = {FLAG: ("j04-fs-audit", "j02-client-onboarding")}
    assert why(raw(), green(1), registry=registry) == [
        "journeys_missing:j02-client-onboarding",
        "journey_never_green:j02-client-onboarding",
    ]


@pytest.mark.parametrize(
    ("slot", "file", "reason"),
    [
        ("2027-09-14T19:00:00-05:00", "flip-2027-09-14-PF-A1.yaml", "no_slot"),  # mini-freeze
        ("2027-09-23T10:00:00-05:00", "flip-2027-09-23-PF-A1.yaml", "no_slot"),  # Thu in window
        ("2027-11-08T10:00:00-06:00", "flip-2027-11-08-PF-A1.yaml", "not_a_release_day"),  # Mon
    ],
)
def test_ac12_the_slot_must_be_one_the_firm_may_flip_in(slot: str, file: str, reason: str) -> None:
    now = datetime.fromisoformat(slot) - timedelta(hours=3)
    found = why(raw(slot=slot), {"j04-fs-audit": now}, file=file, now=now)
    assert found == [reason]


def test_outside_its_window_a_tuesday_or_thursday_is_a_release_day() -> None:
    slot = "2027-11-04T10:00:00-05:00"  # Thu; CDT ends Nov 7
    now = datetime.fromisoformat(slot) - timedelta(hours=3)
    assert (
        why(raw(slot=slot), {"j04-fs-audit": now}, file="flip-2027-11-04-PF-A1.yaml", now=now)
        == []
    )


def test_a_hotfix_needs_no_slot() -> None:
    slot = "2027-09-14T22:00:00-05:00"
    now = datetime.fromisoformat(slot) - timedelta(hours=1)
    request = raw(slot=slot, hotfix="Portal uploads fail for PF-A1 clients")
    assert why(request, {"j04-fs-audit": now}, file="flip-2027-09-14-PF-A1.yaml", now=now) == []


def test_a_firm_that_is_not_a_pilot_firm_or_another_code_is_refused() -> None:
    other = "00000000-0000-4000-8000-0000000000b9"
    assert "not_a_pilot_firm" in why(raw(tenant=other), green(1))
    assert "file_code_is_not_the_firms" in why(raw(), green(1), file="flip-2027-09-21-PF-A2.yaml")


def test_unknown_flags_and_values_and_prompt_variants() -> None:
    assert "unknown_flag" in why(raw(flags=[{"name": "nope.flag", "value": "true"}]), green(1))
    assert "unknown_value" in why(raw(flags=[{"name": FLAG, "value": "maybe"}]), green(1))
    prompt = raw(flags=[{"name": "prompt.screening", "value": "v7"}])
    assert "eval_report_missing" in why(prompt, green(1))
    with_report = raw(
        flags=[{"name": "prompt.screening", "value": "v7"}],
        eval_report="docs/quality/evals/screening@v7.md",
    )
    assert why(with_report, green(1)) == []


@pytest.mark.parametrize(
    ("file", "change", "match"),
    [
        ("flip-PF-A1.yaml", {}, "file is flip-"),
        ("flip-2027-09-22-PF-A1.yaml", {}, "the slot's date"),
        ("flip-2027-09-21-Northwind.yaml", {}, "file is flip-"),
        (
            FILE,
            {"flags": [{"name": FLAG, "value": "true"}, {"name": FLAG, "value": "false"}]},
            "one flag",
        ),
        (FILE, {"kind": "flag_set"}, "kind"),
        (FILE, {"operator": "Ayush K"}, "operator"),
        (FILE, {"slot": "2027-09-21T19:00:00"}, "offset"),
        (FILE, {"journeys": []}, "journeys"),
        (FILE, {"extra": 1}, "unknown"),
    ],
)
def test_malformed_requests_are_refused(file: str, change: dict[str, object], match: str) -> None:
    with pytest.raises(RequestError, match=match):
        parse(raw(**change), file)


def test_merged_it_becomes_the_flag_cli_command_with_its_fingerprint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / FILE
    path.write_text(yaml.safe_dump(raw()), encoding="utf-8")
    assert release.main(["ops-request", str(path)]) == 0
    argv = cast(list[str], json.loads(capsys.readouterr().out))
    assert argv[:3] == ["python", "-m", "abacus_tools.flags"]
    request = parse(yaml.safe_load(path.read_text()), str(path))
    assert argv[argv.index("--request-sha256") + 1] == request.sha256
    assert argv[argv.index("--approved-by") + 1] == "notanaskhan"
    # The flip guard accepts the fingerprint in place of the file and records it.
    verdict = check(
        calendar(),
        Flip(
            firm=request.tenant,
            operator="ayushkbhatia",
            at=request.slot + timedelta(minutes=5),
            flags=(FLAG,),
            approved_by="notanaskhan",
            rollback=request.rollback,
            request_sha256=request.sha256,
        ),
    )
    assert verdict.why == () and verdict.refs["request"] == request.sha256


def test_an_ops_request_may_name_the_flag_cli_since_dec1680(tmp_path: Path) -> None:
    """T-01-T47 (DEC-1680) allowlists the flag CLI for a pilot's go-live; the flip guard, not the
    ops request, still asks for an approver who is not the operator and a rollback."""
    path = tmp_path / "2027-09-21-flag.yaml"
    raw: dict[str, object] = {
        "command": "abacus_tools.flags",
        "args": [],
        "operator": "ayushkbhatia",
        "reason": "x",
    }
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    parsed = release.ops_request(cast(dict[str, object], yaml.safe_load(path.read_text())))
    assert parsed.command == "abacus_tools.flags"
    assert parsed.argv()[:3] == ["python", "-m", "abacus_tools.flags"]


def test_the_cli_precheck_exits_1_naming_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def load(_path: Path = release_windows.WINDOWS_FILE) -> release_windows.Calendar:
        return calendar()

    monkeypatch.setattr(release_windows, "load", load)
    request = tmp_path / FILE
    request.write_text(yaml.safe_dump(raw()), encoding="utf-8")
    journeys = tmp_path / "journeys.json"
    journeys.write_text(json.dumps({"*": (NOW - timedelta(hours=25)).isoformat()}))
    args = ["precheck", str(request), "--journeys", str(journeys), "--now", NOW.isoformat()]
    assert flip_request.main(args) == 1
    assert "journey_stale:j04-fs-audit" in capsys.readouterr().err
    journeys.write_text(json.dumps({"*": (NOW - timedelta(hours=1)).isoformat()}))
    assert flip_request.main(args) == 0
    assert "ready for approval by notanaskhan" in capsys.readouterr().out


def test_the_workflow_runs_flip_precheck_on_the_pr_read_only() -> None:
    workflow = cast(
        dict[object, Any],  # Any: the workflow YAML (`on` parses as True)
        yaml.safe_load((REPO / ".github/workflows/ops-request.yml").read_text()),
    )
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers == {"pull_request": {"paths": ["deploy/production/ops-requests/flip-*.yaml"]}}
    assert workflow["permissions"] == {"contents": "read", "actions": "read"}
    job = workflow["jobs"]["flip-precheck"]
    runs = " ".join(str(s.get("run", "")) for s in job["steps"])
    assert "abacus_tools.flip_request precheck" in runs
    assert "nightly staging journeys" in runs
    for step in job["steps"]:
        uses = str(step.get("uses", ""))
        assert not uses or ("@" in uses and len(uses.split("@")[1].split()[0]) == 40)
