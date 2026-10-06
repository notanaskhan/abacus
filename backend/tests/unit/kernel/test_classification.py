"""AC-20: ADR-031 classification tags and the gate that every model field carries one."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Annotated, get_args

import pytest
from pydantic import BaseModel, Field

import abacus
from abacus.kernel.classification import (
    Classification,
    classified,
    level_of,
    restricted_fields,
    unclassified_fields,
)

LEVELS = ("restricted", "confidential", "internal", "public")


def _all_abacus_models() -> list[type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for info in pkgutil.walk_packages(abacus.__path__, "abacus."):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value is not BaseModel
                and value.__module__ == module.__name__
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return list(found.values())


def test_ac20_classification_has_the_four_adr_031_levels() -> None:
    assert set(get_args(Classification)) == set(LEVELS)


@pytest.mark.parametrize("level", LEVELS)
def test_ac20_classified_sets_cls_in_json_schema_extra(level: str) -> None:
    field = classified(level)  # pyright: ignore[reportArgumentType] -- parametrised literal
    assert field.json_schema_extra == {"cls": level}


def test_ac20_classified_rejects_an_unknown_level() -> None:
    with pytest.raises(ValueError):
        classified("secret")  # pyright: ignore[reportArgumentType] -- deliberately invalid


def test_ac20_classified_works_inside_annotated_and_keeps_required_fields_required() -> None:
    class Probe(BaseModel):
        id: Annotated[int, classified("confidential")]
        note: Annotated[str, classified("restricted")] = ""

    assert unclassified_fields(Probe) == []
    assert Probe.model_fields["id"].is_required()
    assert not Probe.model_fields["note"].is_required()
    assert Probe.model_json_schema()["properties"]["note"]["cls"] == "restricted"
    with pytest.raises(ValueError):
        Probe.model_validate({})


def test_ac20_level_of_returns_the_level_or_none() -> None:
    class Probe(BaseModel):
        a: Annotated[int, classified("internal")]
        b: int

    assert level_of(Probe.model_fields["a"]) == "internal"
    assert level_of(Probe.model_fields["b"]) is None


def test_ac20_restricted_fields_lists_only_restricted_ones() -> None:
    class Probe(BaseModel):
        a: Annotated[int, classified("restricted")]
        b: Annotated[int, classified("confidential")]
        c: Annotated[int, classified("restricted")]
        d: int

    assert sorted(restricted_fields(Probe)) == ["a", "c"]


def test_ac20_gate_flags_an_unclassified_field() -> None:
    class Bad(BaseModel):
        id: int
        tagged: Annotated[int, classified("public")]
        other: str = Field(default="", json_schema_extra={"unrelated": 1})

    assert sorted(unclassified_fields(Bad)) == ["id", "other"]


def test_ac20_gate_passes_a_fully_classified_model() -> None:
    class Good(BaseModel):
        a: Annotated[int, classified("public")]

    assert unclassified_fields(Good) == []


def test_ac20_every_abacus_model_field_is_classified() -> None:
    offenders = {
        f"{model.__module__}.{model.__qualname__}": missing
        for model in _all_abacus_models()
        if (missing := unclassified_fields(model))
    }
    assert offenders == {}
