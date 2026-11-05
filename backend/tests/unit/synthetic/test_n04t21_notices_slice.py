"""N-04-T21 (TASK-3317; DEC-2316): the notices slice's seed counts, from the row.

"make seed-demo produces every NOT artboard's data through service APIs, the fixture and seed exports
are equal, and no template text appears in any migration or constant." The loaded half and the
export equivalence run in the integration pass.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from abacus_tools.synthetic.scenarios.brightwater_hale import notices_content as nc
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events


def test_ac_the_tiles_foot_to_the_seed_counts() -> None:
    assert nc.counts() == {"new": 2, "analyzing": 3, "response_drafted": 2, "awaiting": 2}


def test_ac_the_notice_types_foot() -> None:
    kinds = Counter(
        "State" if n.agency == "state" else n.notice_code for n in nc.NOTICES
    )  # fmt: skip
    assert kinds == {"CP2000": 3, "CP14": 2, "CP501": 1, "State": 3}


def test_ac_the_whitley_row_carries_the_plans_figures() -> None:
    whitley = next(n for n in nc.NOTICES if n.code == "N1")
    assert (whitley.amount, whitley.respond_by.isoformat()) == ("753.01", "2026-09-23")


def test_ac_each_notice_has_a_service_event_and_a_client() -> None:
    events = [e for e in slice_events(nc.SLICE) if e.kind == "notices.seed_notice"]
    assert len(events) == 9
    assert all(e.client for e in events)


def test_ac_the_template_variants_are_content() -> None:
    path = Path(nc.__file__).parent / "files" / "notice_templates.yaml"
    variants = yaml.safe_load(path.read_text())["variants"]
    assert [v["key"] for v in variants] == ["agree", "partial", "disagree", "balance_due", "generic"]
