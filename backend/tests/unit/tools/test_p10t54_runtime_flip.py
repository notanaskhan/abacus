"""P-10-T54 (TASK-7424; DEC-4413): the M17 runtime v2 flip plan, offline.

Row: "M17 flip plan: docs/runbooks/runtime-v2-flip.md (rollback is flags off; runs persist), shadow
of engagement runs on staging and the canary from Mon Mar 20, both founders' approvals for Tue May
2, 2028". The rehearsal on staging and the real request need staging and the founders.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from abacus_tools import flip_request
from abacus_tools import runtime_v2_flip as flip

FIRM = UUID("00000000-0000-4000-8000-0000000000a1")
SHADOW = "https://github.com/notanaskhan/abacus/actions/runs/1"
GOOD = flip.ShadowEvidence(date(2028, 3, 1), date(2028, 4, 20), 64, 0, date(2028, 3, 20))
RENEWED: dict[str, date] = dict.fromkeys(flip.FLAGS_ON, date(2028, 10, 31))
RUNBOOK = Path(__file__).resolve().parents[4] / "docs" / "runbooks" / "runtime-v2-flip.md"


def _requests(**change: object) -> list[flip_request.FlipRequest]:
    out: list[flip_request.FlipRequest] = []
    for name, body in flip.render(FIRM, "PF-A1", SHADOW).items():
        raw = yaml.safe_load(body)
        raw.update(change)
        out.append(flip_request.parse(raw, name))
    return out


def test_render_writes_three_ordered_one_flag_requests_that_parse() -> None:
    files = flip.render(FIRM, "PF-A1", SHADOW)
    assert list(files) == [f"flip-2028-05-02-PF-A1-{n}.yaml" for n in (1, 2, 3)]
    found = _requests()
    assert [r.flag for r in found] == list(flip.FLAGS_ON)
    assert {(r.operator, r.approved_by) for r in found} == {("ayushkbhatia", "notanaskhan")}
    assert all(r.slot == flip.M17_SLOT and r.rollback == flip.ROLLBACK for r in found)


def test_a_complete_plan_with_renewed_flags_and_good_shadow_has_no_findings() -> None:
    assert flip.plan_findings(_requests(), GOOD, RENEWED) == []


def test_rollback_is_the_reverse_order() -> None:
    assert flip.FLAGS_OFF == ("engagement_run.enabled", "realtime.sse", "agent_runtime.v2")


def test_the_registry_flags_expire_before_m17_until_p10_t56_renews_them() -> None:
    expiry = flip.registry_expiry()
    assert set(flip.FLAGS_ON) <= set(expiry)
    found = flip.plan_findings(_requests(), GOOD, expiry)
    assert [f for f in found if f.startswith("flag_expires_before_slot")] == [
        f"flag_expires_before_slot:{name}" for name in flip.FLAGS_ON
    ]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"approved_by": "ayushkbhatia"}, "needs_both_founders:agent_runtime.v2"),
        ({"approved_by": "someone"}, "needs_both_founders:realtime.sse"),
        (
            {"operator": "notanaskhan", "approved_by": "ayushkbhatia"},
            "operator_is_not_the_flag_owner:agent_runtime.v2",
        ),
        (
            {"journeys": ["j11-workbench"]},
            "journeys_missing:agent_runtime.v2:j23-audit-partner-morning",
        ),
        (
            {"rollback": "docs/ops/flips/x.md#rollback"},
            "rollback_is_not_the_runbook:engagement_run.enabled",
        ),
        ({"slot": "2028-05-04T19:00:00-05:00"}, "not_the_m17_slot:realtime.sse"),
    ],
)
def test_each_missing_piece_is_named(change: dict[str, object], reason: str) -> None:
    if "slot" in change:  # a different date is a different file name
        found: list[flip_request.FlipRequest] = []
        for name, body in flip.render(FIRM, "PF-A1", SHADOW).items():
            raw = yaml.safe_load(body)
            raw.update(change)
            found.append(flip_request.parse(raw, name.replace("2028-05-02", "2028-05-04")))
    else:
        found = _requests(**change)
    assert reason in flip.plan_findings(found, GOOD, RENEWED)


def test_a_missing_or_duplicated_flag_and_another_firm_are_named() -> None:
    two = _requests()[:2]
    assert "needs_one_request_per_flag:agent_runtime.v2,realtime.sse,engagement_run.enabled" in (
        flip.plan_findings(two, GOOD, RENEWED)
    )
    mixed = _requests()
    other = flip_request.parse(
        {**yaml.safe_load(flip.render(FIRM, "PF-A1", SHADOW)["flip-2028-05-02-PF-A1-3.yaml"]),
         "tenant": "00000000-0000-4000-8000-0000000000a2"},
        "flip-2028-05-02-PF-A1-3.yaml",
    )  # fmt: skip
    assert "requests_for_more_than_one_firm" in flip.plan_findings(
        [*mixed[:2], other], GOOD, RENEWED
    )


def test_out_of_order_files_are_named() -> None:
    swapped: list[flip_request.FlipRequest] = []
    for name, body in flip.render(FIRM, "PF-A1", SHADOW).items():
        renamed = name.replace("-1.yaml", "-X.yaml").replace("-2.yaml", "-1.yaml")
        swapped.append(flip_request.parse(yaml.safe_load(body), renamed.replace("-X", "-2")))
    found = flip.plan_findings(swapped, GOOD, RENEWED)
    assert "out_of_order:agent_runtime.v2" in found and "out_of_order:realtime.sse" in found


def _ev(start: int, runs: int, failures: int, canary: int | None) -> flip.ShadowEvidence:
    """Shadow from Mar `start` to Apr 20, 2028; the canary from Mar `canary`."""
    first = None if canary is None else date(2028, 3, canary)
    return flip.ShadowEvidence(date(2028, 3, start), date(2028, 4, 20), runs, failures, first)


@pytest.mark.parametrize(
    ("shadow", "reason"),
    [
        (flip.ShadowEvidence(date(2028, 4, 10), date(2028, 4, 20), 64, 0, date(2028, 3, 20)),
         "shadow_under_14_days"),
        (_ev(1, 49, 0, 20), "shadow_under_50_runs"),
        (_ev(1, 64, 1, 20), "shadow_invariant_failures"),
        (_ev(1, 64, 0, 21), "canary_not_running_since_mar_20"),
        (_ev(1, 64, 0, None), "canary_not_running_since_mar_20"),
    ],
)  # fmt: skip
def test_the_shadow_evidence_is_held_to_its_floors(
    shadow: flip.ShadowEvidence, reason: str
) -> None:
    assert flip.plan_findings(_requests(), shadow, RENEWED) == [reason]


def test_an_ordered_suffix_parses_and_others_are_refused() -> None:
    body = yaml.safe_load(flip.render(FIRM, "PF-A1", SHADOW)["flip-2028-05-02-PF-A1-1.yaml"])
    assert flip_request.parse(body, "flip-2028-05-02-PF-A1.yaml").code == "PF-A1"
    for bad in ("flip-2028-05-02-PF-A1-0.yaml", "flip-2028-05-02-PF-A1-10.yaml"):
        with pytest.raises(flip_request.RequestError, match="pilot code"):
            flip_request.parse(body, bad)


def test_the_cli_checks_files_and_shadow_json(tmp_path: Path) -> None:
    flip.main(["render", "--firm", str(FIRM), "--code", "PF-A1", "--shadow-run", SHADOW,
               "--out", str(tmp_path)])  # fmt: skip
    shadow = tmp_path / "shadow.json"
    shadow.write_text(
        '{"shadow_from": "2028-03-01", "shadow_to": "2028-04-20", "runs": 64, '
        '"invariant_failures": 0, "canary_from": "2028-03-20"}',
        encoding="utf-8",
    )
    files = sorted(str(p) for p in tmp_path.glob("flip-*.yaml"))
    # The registry still expires in 2027, so the plan is refused until P-10-T56's renewal.
    assert flip.main(["check", *files, "--shadow", str(shadow)]) == 1


def test_the_runbook_names_the_order_the_rollback_and_both_approvals() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for needle in (*flip.FLAGS_ON, "## Rollback", "notanaskhan", "ayushkbhatia",
                   "Tue May 2, 2028", "Mon Mar 20, 2028", "runs persist"):  # fmt: skip
        assert needle in text, needle


def test_the_shadow_builder_writes_what_check_reads() -> None:
    found = flip.ShadowEvidence(date(2028, 3, 1), date(2028, 4, 20), 64, 0, date(2028, 3, 20))
    again = flip.ShadowEvidence.from_json(json.loads(flip.evidence_json(found)))
    assert again == found
    none = flip.ShadowEvidence(date(2028, 3, 1), date(2028, 4, 20), 64, 0, None)
    assert flip.ShadowEvidence.from_json(json.loads(flip.evidence_json(none))) == none
