"""Q-02-T33 (RB-27): `make incident-propagate` checks Accrued's facts before starting anything."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_tools import incidents

GOOD = {
    "title": "Synthetic sub-processor incident",
    "event_kind": "vendor_incident",
    "discovered_at": "2026-09-10T14:05:00+00:00",
    "confirmed_at": "2026-09-11T09:00:00+00:00",
    "consumers_affected": 0,
    "unencrypted": False,
}


def _file(tmp_path: Path, body: object) -> Path:
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_ac39_the_facts_file_reads_as_the_route_reads_it(tmp_path: Path) -> None:
    facts = incidents.load_facts(_file(tmp_path, GOOD))
    assert facts.event_kind == "vendor_incident"
    assert facts.confirmed_at == "2026-09-11T09:00:00+00:00"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"title": ""}, "title"),
        ({"event_kind": "meteor"}, "event_kind"),
        ({"discovered_at": "2026-09-10T14:05:00"}, "offset"),
        ({"consumers_affected": -1}, "consumers_affected"),
        ({"unencrypted": "yes"}, "unencrypted"),
    ],
)
def test_ac39_bad_facts_are_refused(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    with pytest.raises(incidents.Refused, match=message):
        incidents.load_facts(_file(tmp_path, {**GOOD, **change}))


def test_ac39_a_dry_run_starts_nothing_and_never_prints_the_title(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = incidents.main(
        [
            "propagate",
            "--ref",
            "ACC-2026-001",
            "--firms",
            "00000000-0000-4000-8000-000000000001",
            "--facts",
            str(_file(tmp_path, GOOD)),
            "--staff",
            "00000000-0000-4000-8000-0000000000f1",
            "--reason",
            "Accrued SEV1 confirmed",
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0 and "ACC-2026-001" in out and "Synthetic" not in out
    assert (
        incidents.main(
            [
                "propagate",
                "--ref",
                "acc",
                "--firms",
                "x",
                "--facts",
                "f",
                "--staff",
                "00000000-0000-4000-8000-0000000000f1",
                "--reason",
                "r",
            ]
        )
        == 2
    )
