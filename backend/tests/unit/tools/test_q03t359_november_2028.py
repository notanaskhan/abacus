"""Q-03-T359 (S52; TASK-8855): the November 2028 x100 profile is well formed and loads through the
service APIs: every step names an operation the OpenAPI document has, with its method; the three
loads are there (W1 posting, October 2028 closes, TY2028 season tools); the only writes are the W1
dry run and the post, and the post resends one Idempotency-Key. The runner fills `json_body`
placeholders and replays a step with the same key. The run itself is Q-03-T376's (S54)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus_tools.loadtest import run
from abacus_tools.loadtest.scenario import Scenario, Step

PROFILE = Path(run.__file__).resolve().parent / "scenarios" / "november_2028.yaml"
PATHS = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
VARS = {
    "work_item_id": "w",
    "entry_ids": '["e1", "e2"]',
    "seen_versions": '{"e1": 3, "e2": 1}',
    "client_entity_id": "c",
    "close_id": "k",
    "account_ref": "1000",
    "return_id": "r",
    "tax_year": "2028",
    "manifest_id": "m",
    "cohort_id": "h",
}


def _scenario() -> Scenario:
    return Scenario.model_validate(yaml.safe_load(PROFILE.read_text(encoding="utf-8")))


def test_every_step_is_an_operation_of_the_api() -> None:
    for group in _scenario().groups:
        for step in group.steps:
            path = re.sub(r"\?.*$", "", step.path)
            assert path in PATHS, (group.name, path)
            assert step.method.lower() in PATHS[path], (group.name, step.method, path)


def test_the_three_loads_are_there() -> None:
    paths = {s.path for g in _scenario().groups for s in g.steps}
    assert "/v1/work-items/{work_item_id}/posting-batches" in paths
    assert any(p.startswith("/v1/closes?period=2028-10") for p in paths)
    assert any(p.startswith("/v1/seasons") for p in paths)
    assert any(p.startswith("/v1/filing-deadlines") for p in paths)


def test_the_only_writes_are_the_dry_run_and_one_replayed_post() -> None:
    writes = [s for g in _scenario().groups for s in g.steps if s.method != "GET"]
    assert [(s.path.rsplit("/", 1)[-1], s.idempotency, s.replays) for s in writes] == [
        ("posting-batches:dry-run", False, 0),
        ("posting-batches", True, 1),
    ]


def test_every_group_has_its_target_and_every_var_is_named() -> None:
    scenario = _scenario()
    assert all(g.p95_ms is not None for g in scenario.groups)
    run._paths(scenario, VARS)  # raises on a placeholder without a var


def test_json_body_placeholders_fill_and_parse() -> None:
    body = {"entry_ids": "{entry_ids}", "seen_versions": "{seen_versions}", "note": "x {close_id}"}
    assert run._fill_body(body, VARS) == {
        "entry_ids": ["e1", "e2"],
        "seen_versions": {"e1": 3, "e2": 1},
        "note": "x k",
    }
    with pytest.raises(ValueError, match="needs --var"):
        run._fill_body({"a": "{missing}"}, VARS)


def test_a_replay_needs_a_key() -> None:
    with pytest.raises(ValueError, match="needs idempotency"):
        Step(method="POST", path="/v1/x", replays=1)
