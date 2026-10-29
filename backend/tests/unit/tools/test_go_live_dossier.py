"""Q-04-T021 (and T022's sections): the go-live dossier is chapter 06 §8.3 for one firm.

Acceptance (T021): each PW1 dossier shows every §8.3 item green with evidence and is signed by
both founders by Fri May 28, 2027. These tests pin the dossier's shape (every section by owner,
pilot code only, no contacts), `fill` writing only the generated blocks from `make go-live-check`,
and `--ready` refusing anything short of green, recent and acknowledged.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from abacus_tools import go_live_dossier as gd

REPORT = {
    "pilot_code": "PF-A1",
    "level": "shadow",
    "at": "2027-05-27T10:00:00-05:00",
    "passed": True,
    "failed": [],
    "items": [
        {
            "id": "tenant.provisioned",
            "section": "Tenant",
            "status": "pass",
            "value": "provisioned",
        },
        {
            "id": "identity.sso_enforced",
            "section": "Identity",
            "status": "pass",
            "value": "required",
        },
        {
            "id": "communications.no_client_facing",
            "section": "Operations",
            "status": "pass",
            "value": "none on",
        },
        {
            "id": "integrations.no_writes",
            "section": "Integrations",
            "status": "pass",
            "value": "0",
        },
    ],
}


def test_every_section_of_8_3_is_in_the_template_with_its_owner() -> None:
    text = gd.template("PF-A1")
    assert gd.problems_of("PF-A1", text) == []
    owners = {s.title: s.owner for s in gd.SECTIONS}
    assert owners["Tenant and identity"] == "N" and owners["Communications"] == "AY"
    assert owners["Contract and legal"].startswith("F-09")
    assert {s.key for s in gd.SECTIONS} >= {
        "identity",
        "data",
        "ai",
        "operations",
        "communications",
        "content",
        "integrations",
        "contract",
    }


def test_fill_routes_each_check_to_its_section_and_keeps_the_by_hand_rows() -> None:
    text = gd.fill(gd.template("PF-A1"), REPORT)
    identity = text.split("## Tenant and identity", 1)[1].split("## Data protection", 1)[0]
    comms = text.split("## Communications", 1)[1].split("## Content", 1)[0]
    assert "`tenant.provisioned` | pass" in identity and "`identity.sso_enforced`" in identity
    assert "`communications.no_client_facing`" in comms  # moved out of the tool's Operations
    assert "identity-1 | KMS MRK" in identity
    assert "| Go-live check | shadow at 2027-05-27T10:00:00-05:00, passed |" in text


def test_fill_twice_is_the_same_as_once() -> None:
    once = gd.fill(gd.template("PF-A1"), REPORT)
    assert gd.fill(once, REPORT) == once


@pytest.mark.parametrize(
    ("name", "text_change", "words"),
    [
        ("Okonkwo", "", "named by its pilot code"),
        ("PF-A1", "qi@example.test", "an email address"),
        ("PF-A1", "512-555-0147", "a phone number"),
    ],
)
def test_the_dossier_holds_no_names_and_no_contacts(
    name: str, text_change: str, words: str
) -> None:
    text = gd.template("PF-A1") + text_change
    assert any(words in p for p in gd.problems_of(name, text))


def test_a_missing_section_or_block_is_refused() -> None:
    text = gd.template("PF-A1").replace(gd.end_marker("data"), "")
    assert any("generated block is missing" in p for p in gd.problems_of("PF-A1", text))


def _ready_text() -> str:
    text = gd.fill(gd.template("PF-A1"), REPORT)
    lines = []
    for line in text.splitlines():
        cells = line.split(" | ")
        if (
            line.startswith("| ")
            and len(cells) == 4
            and cells[0][2:].split("-")[0] in {s.key for s in gd.SECTIONS}
        ):
            line = f"{cells[0]} | {cells[1]} | V-123 | green |"
        lines.append(line)
    text = "\n".join(lines) + "\n"
    return text.replace("| — | — | — |", "| 2027-05-20 | shadow-briefing v1 | V-124 |", 1)


def test_ready_needs_every_row_green_a_recent_passing_check_and_the_acknowledgement() -> None:
    day = date(2027, 5, 28)
    assert gd.not_ready("PF-A1", _ready_text(), day) == []
    assert any(
        "not green" in p for p in gd.not_ready("PF-A1", gd.fill(gd.template("PF-A1"), REPORT), day)
    )
    assert any(
        "older than 7 days" in p for p in gd.not_ready("PF-A1", _ready_text(), date(2027, 6, 10))
    )
    failed = _ready_text().replace(", passed |", ", failed: identity.sso_enforced |")
    assert any("check failed" in p for p in gd.not_ready("PF-A1", failed, day))
    unacked = _ready_text().replace("| 2027-05-20 | shadow-briefing v1 | V-124 |", "| — | — | — |")
    assert any("not acknowledged" in p for p in gd.not_ready("PF-A1", unacked, day))


def test_new_and_fill_refuse_a_name_or_another_firms_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gd, "DOSSIERS", tmp_path)
    assert gd.main(["new", "Okonkwo"]) == 2
    assert gd.main(["new", "PF-A1"]) == 0 and gd.main(["new", "PF-A1"]) == 2
    other = tmp_path / "r.json"
    other.write_text(json.dumps({**REPORT, "pilot_code": "PF-A2"}), encoding="utf-8")
    assert gd.main(["fill", "PF-A1", "--report", str(other)]) == 2
    mine = tmp_path / "m.json"
    mine.write_text(json.dumps(REPORT), encoding="utf-8")
    assert gd.main(["fill", "PF-A1", "--report", str(mine)]) == 0
    assert gd.main(["check"]) == 0


@pytest.mark.source_scan
def test_the_committed_template_matches_the_tool() -> None:
    committed = (gd.DOSSIERS / "_TEMPLATE.md").read_text(encoding="utf-8")
    assert committed == gd.template("<pilot-code>")
