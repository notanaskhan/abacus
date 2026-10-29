# ac-test-author: ayushkbhatia
"""A-02-T32 (TASK-1745; ADR-044; chapter 10 §10.7.4; DEC-835): a drifted fake marks the journeys
that depend on it unverified in the weekly quality report, and CI blocks a recording that holds a
real identifier.

- The nightly job records each target's outcome (`connector_conformance record`); a sandbox that
  fails while the fake passes makes J02, J05 and J10 (chapter 10 §10.6.6's QBO journeys)
  "unverified" in the report's Contracts area, a breach; a sandbox skipped for want of credentials
  or a fake that also fails is not drift; a failing fake is reported on its own.
- The recordings in the tree are clean, and each real-identifier shape is caught in a seeded
  recording (a token, a company id that is not synthetic, a real mailbox, a real phone number, the
  production host).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest

from abacus_tools.quality import connector_conformance as cc
from abacus_tools.quality import report as rp

from . import targets

WINDOW = rp.Window(date(2027, 5, 3), date(2027, 5, 14))


def _results(fake: str, sandbox: str) -> dict[str, object]:
    return {"providers": {"quickbooks_online": {"fake": fake, "sandbox": sandbox}}}


def _row(connectors: object) -> rp.Row:
    rows = list(rp.contract_rows(rp.REPO, connectors))
    return next(r for r in rows if r.metric == "Unverified fakes")


# --- Drift --------------------------------------------------------------------------------------


def test_ac_a_drifted_fake_marks_its_journeys_unverified_in_the_report() -> None:
    drifted = cc.unverified(_results("passed", "failed"))
    assert drifted == [cc.Unverified("quickbooks_online", ("J02", "J05", "J10"))]
    row = _row(_results("passed", "failed"))
    assert row.area == "Contracts"
    assert row.status == "breach"
    assert row.value == "1: quickbooks_online (journeys unverified: J02, J05, J10)"


@pytest.mark.parametrize(
    ("fake", "sandbox"),
    [("passed", "passed"), ("passed", "skipped"), ("failed", "failed"), ("failed", "passed")],
)
def test_no_drift_unless_the_sandbox_fails_while_the_fake_passes(fake: str, sandbox: str) -> None:
    assert cc.unverified(_results(fake, sandbox)) == []


def test_a_failing_fake_is_reported_as_a_breach_of_its_own() -> None:
    row = _row(_results("failed", "skipped"))
    assert (row.value, row.status) == ("0: quickbooks_online (fake failing)", "breach")


def test_a_clean_night_reads_zero_and_no_results_read_no_data() -> None:
    assert (
        _row(_results("passed", "passed")).value,
        _row(_results("passed", "passed")).status,
    ) == (
        "0",
        "ok",
    )
    assert _row(None).value == "no data"
    assert cc.unverified({"providers": "garbled"}) == []
    assert cc.unverified([]) == []


def test_the_report_reads_connectors_json_from_its_inputs(tmp_path: Path) -> None:
    (tmp_path / "connectors.json").write_text(json.dumps(_results("passed", "failed")))
    rows = rp.build(tmp_path, WINDOW)
    row = next(r for r in rows if r.metric == "Unverified fakes")
    assert row.status == "breach"
    assert "J02, J05, J10" in row.value


def test_record_merges_one_provider_and_keeps_the_others(tmp_path: Path) -> None:
    out = tmp_path / "connectors.json"
    out.write_text(
        json.dumps({"providers": {"docusign": {"fake": "passed", "sandbox": "passed"}}})
    )
    when = datetime(2027, 5, 7, 8, tzinfo=UTC)
    document = cc.record(out, "quickbooks_online", "passed", "failed", now=when)
    providers = document["providers"]
    assert isinstance(providers, dict)
    assert set(cast(dict[str, object], providers)) == {"docusign", "quickbooks_online"}
    assert json.loads(out.read_text())["providers"]["quickbooks_online"] == {
        "fake": "passed",
        "sandbox": "failed",
        "finished_at": "2027-05-07T08:00:00+00:00",
    }
    with pytest.raises(ValueError, match="outcome"):
        cc.record(out, "quickbooks_online", "passed", "maybe")  # type: ignore[arg-type]  # a refused outcome


def test_the_record_command_prints_the_unverified_journeys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "connectors.json"
    argv = ["record", "--provider", "quickbooks_online", "--fake", "passed"]
    assert cc.main([*argv, "--sandbox", "failed", "--out", str(out)]) == 0
    assert "quickbooks_online: fake drifted; unverified: J02, J05, J10" in capsys.readouterr().out
    assert cc.main([*argv, "--sandbox", "passed", "--out", str(out)]) == 0
    assert capsys.readouterr().out == ""


# --- The real-identifier block ------------------------------------------------------------------


def test_ac_the_recordings_in_the_tree_are_clean_and_include_this_suites() -> None:
    found = cc.recordings()
    assert targets.RECORDING in found
    assert cc.scan(found) == []
    assert cc.main(["scan"]) == 0


@pytest.mark.parametrize(
    ("planted", "named"),
    [
        ('"access_token": "eyJhbGciOiJkaXIi.eyJleHAiOjE3MDAw.abc"', "JWT-shaped"),
        ('"refresh_token": "AB11730000000000aBcDeFgHiJkLmNoPqRsTuVwX"', "Intuit-shaped"),
        ('"realmId": "9130354677812345"', "not a synthetic realm"),
        ('"PrimaryEmailAddr": "controller@copperleaf-books.com"', "reserved example domains"),
        ('"PrimaryPhone": "(415) 867-5309"', "phone number"),
        ('"href": "https://quickbooks.api.intuit.com/v3/company/1"', "production QuickBooks"),
    ],
)
def test_ac_a_seeded_real_identifier_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: str, named: str
) -> None:
    recording = tmp_path / "backend/tests/connectors/quickbooks_online/recordings/seeded.json"
    recording.parent.mkdir(parents=True)
    recording.write_text("{\n  " + planted + "\n}\n")
    problems = cc.scan(cc.recordings(tmp_path), tmp_path)
    assert len(problems) == 1, problems
    assert named in problems[0]
    assert problems[0].startswith("backend/tests/connectors/quickbooks_online/recordings/seeded")
    monkeypatch.setattr(cc, "REPO", tmp_path)
    assert cc.main(["scan"]) == 1


@pytest.mark.parametrize(
    "allowed",
    [
        '"PrimaryEmailAddr": "books@copperleaf.example.com"',
        '"Email": "grace@brightwater.test"',
        '"PrimaryPhone": "(415) 555-0142"',
        '"realmId": "1234567890123450"',
        '"href": "https://sandbox-quickbooks.api.intuit.com/v3/company/1"',
        '{"value": "152340.18"}',
    ],
)
def test_synthetic_values_pass_the_block(allowed: str) -> None:
    assert cc.findings(allowed) == []


def test_a_binary_recording_cannot_be_checked_so_it_is_refused(tmp_path: Path) -> None:
    recording = tmp_path / "backend/tests/connectors/quickbooks_online/recordings/blob.bin"
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b"\xff\xfe\x00binary")
    problems = cc.scan([recording], tmp_path)
    assert problems == [
        "backend/tests/connectors/quickbooks_online/recordings/blob.bin: not UTF-8 text, so it "
        "cannot be checked"
    ]
