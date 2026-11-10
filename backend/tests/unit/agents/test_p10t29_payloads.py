"""P-10-T29: every value AgentRunWorkflow passes across the activity boundary survives Temporal's
default payload converter. `dict[str, object]` does not (the converter decodes `Any`, not
`object`), and a run failed at its first activity with "Failed decoding arguments" until the
recorder caught it."""

from __future__ import annotations

import inspect

import pytest
from temporalio.converter import DataConverter

from abacus.modules.agents.run_activities import (
    RUN_V2_ACTIVITIES,
    PlanState,
    RunFacts,
    StepOutcome,
)

STEP: dict[str, object] = {
    "key": "narrate",
    "label": "Narrate",
    "level": 0,
    "kind": "narration",
    "arguments": {},
}


@pytest.mark.parametrize(
    "value",
    [
        RunFacts("queued", "e", ["c"], ["w"], {"t": "a"}, 2, [STEP], [("w", "u")]),
        PlanState(1, "approved", [STEP]),
        StepOutcome("succeeded", None, 3, 40),
    ],
    ids=["RunFacts", "PlanState", "StepOutcome"],
)
def test_the_results_round_trip(value: object) -> None:
    convert = DataConverter.default.payload_converter
    back = convert.from_payloads(convert.to_payloads([value]), [type(value)])
    assert back == [value]


@pytest.mark.parametrize("fn", RUN_V2_ACTIVITIES, ids=lambda f: f.__name__)
def test_no_activity_parameter_is_an_object_dict(fn: object) -> None:
    hints = inspect.get_annotations(fn, eval_str=True)  # type: ignore[arg-type] -- an activity function
    assert not [n for n, h in hints.items() if "object" in str(h) and "dict" in str(h)], hints
