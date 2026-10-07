"""AC-1: the per-class worker limits in settings (TASK-018 contract revision 1, "Settings").

`work_classes` holds exactly the four classes, each with `max_activities` and
`max_workflow_tasks` of at least 1. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from abacus.kernel.config import Settings, WorkClassLimits, settings

DEFAULTS = {
    "interactive": (10, 10),
    "time_sensitive": (10, 10),
    "background": (5, 5),
    "batch": (2, 2),
}


# TASK-018b: each class's slot caps and maximum wait are required fields; 018c adds the
# admission reserve.
SLOTS = {
    "interactive": {
        "firm_cap": 20,
        "engagement_cap": 10,
        "class_capacity": 50,
        "max_wait_seconds": 120,
        "admission_reserve_pct": 0,
    },
    "time_sensitive": {
        "firm_cap": 20,
        "engagement_cap": 10,
        "class_capacity": 50,
        "max_wait_seconds": 600,
        "admission_reserve_pct": 0,
    },
    "background": {
        "firm_cap": 10,
        "engagement_cap": 5,
        "class_capacity": 20,
        "max_wait_seconds": 21600,
        "admission_reserve_pct": 25,
    },
    "batch": {
        "firm_cap": 5,
        "engagement_cap": 2,
        "class_capacity": 10,
        "max_wait_seconds": 86400,
        "admission_reserve_pct": 50,
    },
}


def _limits(**overrides: tuple[int, int]) -> dict[str, dict[str, int]]:
    merged = {**DEFAULTS, **overrides}
    return {
        c: {"max_activities": a, "max_workflow_tasks": t, **SLOTS[c]}
        for c, (a, t) in merged.items()
    }


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    settings.cache_clear()
    yield
    settings.cache_clear()


def _load(monkeypatch: pytest.MonkeyPatch, value: object) -> Settings:
    monkeypatch.setenv("ABACUS_WORK_CLASSES", json.dumps(value))
    settings.cache_clear()
    return settings()


def test_ac1_the_defaults_are_small_enough_for_the_database_pool() -> None:
    found = settings().work_classes
    assert {c: (v.max_activities, v.max_workflow_tasks) for c, v in found.items()} == DEFAULTS
    assert list(found) == ["interactive", "time_sensitive", "background", "batch"]


def test_ac1_an_override_names_all_four_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    found = _load(monkeypatch, _limits(background=(1, 3))).work_classes
    assert found["background"] == WorkClassLimits(
        max_activities=1, max_workflow_tasks=3, **SLOTS["background"]
    )
    assert found["interactive"] == WorkClassLimits(
        max_activities=10, max_workflow_tasks=10, **SLOTS["interactive"]
    )


@pytest.mark.parametrize("missing", ["interactive", "time_sensitive", "background", "batch"])
def test_ac1_settings_without_one_of_the_classes_are_refused(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    value = _limits()
    del value[missing]
    with pytest.raises(ValidationError):
        _load(monkeypatch, value)


def test_ac1_an_extra_class_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    value: dict[str, object] = {
        **_limits(),
        "urgent": {"max_activities": 1, "max_workflow_tasks": 1},
    }
    with pytest.raises(ValidationError):
        _load(monkeypatch, value)


@pytest.mark.parametrize("field", ["max_activities", "max_workflow_tasks"])
@pytest.mark.parametrize("bad", [0, -1])
def test_ac1_a_limit_below_one_is_refused(
    monkeypatch: pytest.MonkeyPatch, field: str, bad: int
) -> None:
    value = _limits()
    value["batch"][field] = bad
    with pytest.raises(ValidationError):
        _load(monkeypatch, value)


def test_ac1_a_limit_of_one_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    found = _load(monkeypatch, _limits(background=(1, 1))).work_classes
    assert found["background"].max_activities == 1


def test_ac1_a_limit_with_an_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        WorkClassLimits.model_validate(
            {"max_activities": 1, "max_workflow_tasks": 1, "max_everything": 9}
        )


def test_ac1_a_limit_missing_a_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        WorkClassLimits.model_validate({"max_activities": 1})


def test_ac1_limits_are_immutable() -> None:
    with pytest.raises(ValidationError):
        settings().work_classes["batch"].max_activities = 99
