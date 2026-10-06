"""AC-14, AC-17: agent specs and their code generation (TASK-011a interface contract, "Agent
specs"; ADR-005, ADR-047).

A spec is validated at import: unknown keys, an unregistered prompt, a task scope holding an action
the matrix does not give agents, or any autonomy but `propose` all fail. The generated `_specs.py`
must match the YAML. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import copy
import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from abacus.ai_gateway import UnknownPrompt, prompt
from abacus.modules.agents import spec as spec_module
from abacus.modules.agents.api import AGENTS, SCREENER, AgentSpec, spec
from abacus.modules.agents.specs import _specs
from abacus.modules.identity.api import agent_may_hold
from abacus.modules.identity.authz import UnknownAction
from abacus_tools.codegen import agent_specs

REPO = Path(__file__).resolve().parents[4]
BACKEND = REPO / "backend"
SPECS_DIR = Path(_specs.__file__).parent
SCREENER_YAML = SPECS_DIR / "evidence.screener.yaml"
# Specs whose evaluation suite is delivered by a later increment (011b), by evaluation_suite path.
OWED_TO_011B = {"evals/screening"}
# The loader that runs at import, reached by name: tests drive it with patched SPECS.
load_specs = cast(Callable[[], dict[str, AgentSpec]], vars(spec_module)["_load"])


def _raw() -> dict[str, object]:
    return copy.deepcopy(_specs.SPECS[SCREENER])


def _with(raw: dict[str, object], **changes: object) -> dict[str, dict[str, object]]:
    return {SCREENER: {**raw, **changes}}


# --- the screener ------------------------------------------------------------------------------


def test_ac14_the_screener_is_registered_from_its_spec() -> None:
    assert set(AGENTS) == set(_specs.SPECS)
    assert SCREENER == "evidence.screener"
    found = spec(SCREENER)
    assert found is AGENTS[SCREENER]
    assert isinstance(found, AgentSpec)
    assert found.id == SCREENER


def test_ac14_the_screener_reads_its_prompt_tier_and_scope_from_the_spec() -> None:
    found = spec(SCREENER)
    assert found.prompt == "evidence.screen@v0"
    assert found.tier == "small"
    assert found.task_scope == frozenset({"evidence.read", "screening.run"})
    assert found.autonomy == "propose"
    assert found.untrusted_inputs == frozenset({"account_names"})


def test_ac14_the_screener_routes_low_confidence_to_needs_revision() -> None:
    routing = spec(SCREENER).confidence_routing
    assert routing.below == Decimal("0.5")
    assert routing.route == "needs_revision"


def test_ac16_the_screener_has_a_single_step_budget_of_three_cents() -> None:
    limits = spec(SCREENER).limits
    assert limits.max_cost_usd == Decimal("0.03")
    assert limits.max_steps == 1
    assert limits.max_output_tokens > 0
    assert limits.max_seconds > 0


def test_ac14_an_unknown_agent_is_a_lookup_error() -> None:
    with pytest.raises(LookupError):
        spec("evidence.nothing")
    with pytest.raises(LookupError):
        spec("")


def test_ac14_a_spec_is_immutable() -> None:
    with pytest.raises(ValidationError):
        AGENTS[SCREENER].autonomy = "propose"


@pytest.mark.parametrize("agent_id", sorted(_specs.SPECS))
def test_ac14_every_spec_names_a_registered_prompt_version(agent_id: str) -> None:
    assert prompt(AGENTS[agent_id].prompt).ref == AGENTS[agent_id].prompt


@pytest.mark.parametrize("agent_id", sorted(_specs.SPECS))
def test_ac17_every_spec_proposes_and_only_holds_actions_agents_may_hold(agent_id: str) -> None:
    found = AGENTS[agent_id]
    assert found.autonomy == "propose"
    assert found.task_scope
    assert all(agent_may_hold(action) for action in found.task_scope)


@pytest.mark.parametrize("agent_id", sorted(_specs.SPECS))
def test_ac14_every_spec_has_an_evaluation_suite_that_exists_or_is_owed(agent_id: str) -> None:
    suite = AGENTS[agent_id].evaluation_suite
    assert (REPO / suite).exists() or suite in OWED_TO_011B


def test_ac14_the_owed_list_names_only_suites_that_are_still_missing() -> None:
    assert all(not (REPO / suite).exists() for suite in OWED_TO_011B)


# --- validation ----------------------------------------------------------------------------------


def test_ac14_the_stock_spec_validates() -> None:
    assert AgentSpec.model_validate(_raw()).id == SCREENER


def test_ac14_the_stock_specs_load() -> None:
    assert set(load_specs()) == set(_specs.SPECS)


@pytest.mark.parametrize(
    "changes",
    [
        {"unexpected": "x"},
        {"autonomy": "act"},
        {"autonomy": "decide"},
        {"autonomy": "PROPOSE"},
        {"autonomy": ""},
        {"shape": "multi_step"},
        {"tier": "huge"},
        {"escalation_tier": "huge"},
        {"id": "Evidence.Screener"},
        {"id": "screener"},
        {"id": ""},
        {"version": 0},
        {"purpose": ""},
        {"evaluation_suite": "../evals/screening"},
        {"evaluation_suite": "screening"},
        {
            "limits": {
                "max_output_tokens": 800,
                "max_cost_usd": "0",
                "max_steps": 1,
                "max_seconds": 1,
            }
        },
        {
            "limits": {
                "max_output_tokens": 800,
                "max_cost_usd": "-1",
                "max_steps": 1,
                "max_seconds": 1,
            }
        },
        {
            "limits": {
                "max_output_tokens": 800,
                "max_cost_usd": "0.03",
                "max_steps": 0,
                "max_seconds": 1,
            }
        },
        {
            "limits": {
                "max_output_tokens": 800,
                "max_cost_usd": "0.03",
                "max_steps": 1,
                "max_seconds": 60,
                "unexpected": 1,
            }
        },
        {"confidence_routing": {"below": "1.5", "route": "needs_revision"}},
        {"confidence_routing": {"below": "0.5", "route": "accepted"}},
    ],
    ids=lambda changes: "-".join(sorted(changes)) + ":" + str(next(iter(changes.values())))[:40],
)
def test_ac14_an_invalid_spec_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({**_raw(), **changes})


@pytest.mark.parametrize(
    "missing",
    sorted(k for k in _raw()),
)
def test_ac14_a_spec_missing_a_field_is_refused(missing: str) -> None:
    raw = _raw()
    del raw[missing]
    with pytest.raises(ValidationError):
        AgentSpec.model_validate(raw)


def test_ac14_a_spec_with_an_unknown_key_fails_when_specs_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spec_module, "SPECS", _with(_raw(), surprise=True))
    with pytest.raises(ValidationError):
        load_specs()


def test_ac14_a_spec_naming_an_unregistered_prompt_fails_when_specs_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spec_module, "SPECS", _with(_raw(), prompt="evidence.screen@v99"))
    with pytest.raises(UnknownPrompt):
        load_specs()


@pytest.mark.parametrize(
    "action",
    [
        "evidence.accept",
        "evidence.reject",
        "fulfilment.confirm",
        "suggestion.resolve",
        "follow_up.send",
        "evidence.upload",
        "request_item.mark_ready",
        "connection.pull",
    ],
)
def test_ac17_a_task_scope_holding_an_action_agents_may_not_hold_fails_when_specs_are_loaded(
    monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    scope = ["evidence.read", "screening.run", action]
    monkeypatch.setattr(spec_module, "SPECS", _with(_raw(), task_scope=scope))
    with pytest.raises(ValueError, match="task scope"):
        load_specs()


def test_ac17_a_task_scope_holding_an_action_the_matrix_does_not_know_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        spec_module, "SPECS", _with(_raw(), task_scope=["evidence.read", "evidence.invent"])
    )
    with pytest.raises((ValueError, UnknownAction)):
        load_specs()


def test_ac17_autonomy_other_than_propose_fails_when_specs_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spec_module, "SPECS", _with(_raw(), autonomy="act"))
    with pytest.raises(ValidationError):
        load_specs()


# --- generation and drift ------------------------------------------------------------------------


def test_ac14_the_generated_specs_match_the_yaml_files() -> None:
    assert agent_specs.render() == (SPECS_DIR / "_specs.py").read_text()
    assert agent_specs.main(["--check"]) == 0


def test_ac14_the_yaml_files_and_the_generated_ids_agree() -> None:
    ids = {
        str(cast(dict[str, object], yaml.safe_load(path.read_text()))["id"])
        for path in SPECS_DIR.glob("*.yaml")
    }
    assert ids == set(_specs.SPECS)
    for path in SPECS_DIR.glob("*.yaml"):
        document = cast(dict[str, object], yaml.safe_load(path.read_text()))
        assert path.stem == document["id"]


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the specs directory the generator is pointed at: the real files stay untouched."""
    directory = tmp_path / "specs"
    shutil.copytree(SPECS_DIR, directory, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(agent_specs, "SPECS_DIR", directory)
    monkeypatch.setattr(agent_specs, "TARGET", directory / "_specs.py")
    monkeypatch.setattr(agent_specs, "BACKEND", tmp_path)  # the drift message is relative to it
    return directory


def test_ac14_a_yaml_edit_makes_the_drift_check_fail_until_regenerated(scratch: Path) -> None:
    real_before = (SPECS_DIR / "_specs.py").read_bytes()
    assert agent_specs.main(["--check"]) == 0
    edited = scratch / "evidence.screener.yaml"
    edited.write_text(edited.read_text().replace("tier: small", "tier: medium", 1))
    assert agent_specs.main(["--check"]) == 1
    assert agent_specs.main([]) == 0
    assert agent_specs.main(["--check"]) == 0
    assert "'tier': 'medium'" in (scratch / "_specs.py").read_text()
    assert (SPECS_DIR / "_specs.py").read_bytes() == real_before


def test_ac14_a_hand_edited_generated_file_fails_the_drift_check(scratch: Path) -> None:
    target = scratch / "_specs.py"
    target.write_text(target.read_text() + "\n# hand edit\n")
    assert agent_specs.main(["--check"]) == 1


def test_ac14_a_missing_generated_file_fails_the_drift_check(scratch: Path) -> None:
    (scratch / "_specs.py").unlink()
    assert agent_specs.main(["--check"]) == 1


def test_ac14_a_new_yaml_spec_makes_the_drift_check_fail(scratch: Path) -> None:
    source = scratch / "evidence.screener.yaml"
    (scratch / "evidence.other.yaml").write_text(
        source.read_text().replace("id: evidence.screener", "id: evidence.other")
    )
    assert agent_specs.main(["--check"]) == 1


def test_ac14_generation_is_deterministic(scratch: Path) -> None:
    assert agent_specs.render() == agent_specs.render()
    assert agent_specs.main([]) == 0
    first = (scratch / "_specs.py").read_text()
    assert agent_specs.main([]) == 0
    assert (scratch / "_specs.py").read_text() == first
    assert first == (SPECS_DIR / "_specs.py").read_text()


def test_ac14_the_real_generated_file_is_untouched_by_these_tests() -> None:
    assert agent_specs.render() == (SPECS_DIR / "_specs.py").read_text()
