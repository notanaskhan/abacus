"""F-04-T09 (F-04.14; DEC-19, D9, D10, X-01, X-02): the scenario package is registered with F-02's
scope guard, and the built scenario has no single audit or Yellow Book engagement and no ESG, bank
regulator or sanctions framework row."""

from __future__ import annotations

import json

import pytest

from abacus_tools.quality import scope_guards as sg
from abacus_tools.synthetic.scenarios.brightwater_hale import build
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import AUDITS

GUARDS = sg.load()


@pytest.mark.source_scan
def test_t09_the_scope_guard_scans_the_scenario_package() -> None:
    assert [p.relative_to(sg.REPO).as_posix() for p in sg.SCENARIOS] == [
        "backend/src/abacus_tools/synthetic/scenarios"
    ]
    # A guard on an identifier the scenario's Python uses reaches it: the package is scanned.
    probe = sg.load(sg.SOURCE.read_text().replace("[yellow_book,", "[holdout, yellow_book,"))
    scanned = {f.path for f in sg.scan(probe)}
    assert any(p.startswith("backend/src/abacus_tools/synthetic/scenarios/") for p in scanned)


def test_t09_no_excluded_engagement_type_in_the_scenario() -> None:
    types = {a.type for a in AUDITS}
    assert not types & {"single_audit", "yellow_book", "gagas"}
    assert len(AUDITS) == 27


def test_t09_no_excluded_framework_in_the_built_scenario() -> None:
    for snapshot in ("E0", "2026-09-24"):
        text = json.dumps(build(snapshot).canonical())
        assert list(sg.excluded_in(text, GUARDS, "scenario")) == []
        lowered = text.lower()
        for key in ("esg", "ffiec", "nydfs", "ofac"):
            assert f'"{key}"' not in lowered
