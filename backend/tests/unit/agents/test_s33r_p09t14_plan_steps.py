"""P-09-T14 (DEC-3142): the run header carries the newest plan's steps for "Change order…";
a metadata reader gets none."""

from __future__ import annotations

import uuid

from abacus.modules.agents.run_views import V2Facts, step_labels
from abacus.modules.agents.runs import Counters, _header  # pyright: ignore[reportPrivateUsage]
from abacus.modules.agents.runs_routes import RunHeaderOut


def test_step_labels_keep_order_and_drop_malformed_entries() -> None:
    raw = [
        {"key": "tb", "label": "Read trial balance", "level": 0},
        {"key": "x"},
        "junk",
        {"key": "risk", "label": "Assess risks", "level": 1},
    ]
    assert step_labels(raw) == (("tb", "Read trial balance"), ("risk", "Assess risks"))
    assert step_labels(None) == ()


def _facts() -> V2Facts:
    return V2Facts(
        uuid.uuid4(),
        3,
        "needs_input",
        None,
        {"kind": "approval"},
        Counters(0, 0, 0, 0, 0, 0),
        None,
        "manual",
        "WI-1",
        uuid.uuid4(),
        True,
        2,
        (("tb", "Read trial balance"),),
    )


def test_the_header_carries_the_steps_and_metadata_readers_get_none() -> None:
    assert _header(_facts(), {}, metadata=False).plan_steps == (("tb", "Read trial balance"),)
    assert _header(_facts(), {}, metadata=True).plan_steps == ()
    assert "plan_steps" in RunHeaderOut.model_fields
