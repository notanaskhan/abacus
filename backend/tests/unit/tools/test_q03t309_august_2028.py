"""Q-03-T309 (S46): the August 2028 load profile is well formed and loads through the service
APIs: every step names an operation the OpenAPI document has, with its method; the four loads are
there (1065 entity returns, Workbench sessions, July 2028 closes, the 1,500 SSE streams); the only
write is a Workbench message, idempotent. The run itself is the perf stack's (not in S46)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import yaml

from abacus.api.export_openapi import document
from abacus_tools.loadtest.scenario import Scenario

PROFILE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "abacus_tools"
    / "loadtest"
    / "scenarios"
    / "august_2028.yaml"
)
PATHS = cast(dict[str, dict[str, object]], json.loads(document())["paths"])


def _scenario() -> Scenario:
    return Scenario.model_validate(yaml.safe_load(PROFILE.read_text(encoding="utf-8")))


def _template(path: str) -> str:
    """A step's path as the document names it: `{var}` placeholders kept, the query dropped."""
    bare = path.split("?", 1)[0]
    return re.sub(r"\{([a-z_]+)\}", lambda m: "{" + m.group(1) + "}", bare)


def test_every_step_is_an_operation_of_the_api() -> None:
    for group in _scenario().groups:
        for step in group.steps:
            path = _template(step.path)
            assert path in PATHS, (group.name, path)
            assert step.method.lower() in PATHS[path], (group.name, step.method, path)


def test_the_four_loads_are_there() -> None:
    scenario = _scenario()
    paths = {s.path for g in scenario.groups for s in g.steps}
    assert any(p.startswith("/v1/tax-returns/{return_id}/schedules/k") for p in paths)
    assert any(p.startswith("/v1/workbench/sessions") for p in paths)
    assert any(p.startswith("/v1/closes") for p in paths)
    assert [(s.count, s.hold_seconds) for s in scenario.streams] == [(1500, 1800)]


def test_the_only_write_is_an_idempotent_workbench_message() -> None:
    writes = [s for g in _scenario().groups for s in g.steps if s.method != "GET"]
    assert [(s.method, s.path, s.idempotency) for s in writes] == [
        ("POST", "/v1/workbench/sessions/{session_id}/messages", True)
    ]


def test_every_group_has_its_target() -> None:
    assert all(g.p95_ms is not None for g in _scenario().groups)
