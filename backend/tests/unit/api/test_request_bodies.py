"""ASVS 4.0.3 V5.1.2 and V13.2.2 (Q-03-T017): every JSON request body refuses undeclared fields.

Input models are `extra="forbid"` (`docs/architecture/reference/backend-module.md`), so a client
can never smuggle a field past the model, and a renamed field fails loudly instead of being
ignored. Read off the generated OpenAPI document, so a new route is covered the day it lands.
"""

from __future__ import annotations

import json
from typing import Final, cast

import pytest

from abacus.api.export_openapi import document

Json = dict[str, object]
METHODS: Final = {"get", "post", "put", "patch", "delete"}

# Bodies held as strict xfails with a cited defect. ED-034 (`PUT /v1/firm/letter-policy` read its
# output model) was fixed with `LetterPolicyIn` (TASK-1202); keep the mechanism for the next one.
HELD: Final[dict[tuple[str, str], pytest.MarkDecorator]] = {}


DOCUMENT: Final = cast(Json, json.loads(document()))
SCHEMAS: Final = cast(dict[str, Json], cast(Json, DOCUMENT["components"])["schemas"])


def _refs(schema: Json) -> list[str]:
    """The component names a body schema points at: a `$ref`, or the refs of an optional body."""
    if "$ref" in schema:
        return [str(schema["$ref"]).rsplit("/", 1)[-1]]
    found: list[str] = []
    for option in cast(list[Json], schema.get("anyOf", [])):
        found += _refs(option)
    return found


def _bodies() -> list[tuple[str, str, Json]]:
    paths = cast(dict[str, dict[str, Json]], DOCUMENT["paths"])
    found: list[tuple[str, str, Json]] = []
    for path, operations in sorted(paths.items()):
        for method, operation in sorted(operations.items()):
            if method not in METHODS or "requestBody" not in operation:
                continue
            content = cast(dict[str, Json], cast(Json, operation["requestBody"])["content"])
            if "application/json" in content:
                found.append((method, path, cast(Json, content["application/json"]["schema"])))
    return found


BODIES: Final = _bodies()


def test_there_are_json_request_bodies_to_check() -> None:
    assert len(BODIES) > 100


@pytest.mark.parametrize(
    ("method", "path", "schema"),
    [pytest.param(m, p, s, id=f"{m} {p}", marks=HELD.get((m, p), ())) for m, p, s in BODIES],
)
def test_asvs_5_1_2_the_body_forbids_undeclared_fields(
    method: str, path: str, schema: Json
) -> None:
    names = _refs(schema)
    assert names, f"{method} {path}: the body is not a named model"
    for name in names:
        assert SCHEMAS[name].get("additionalProperties") is False, f"{method} {path}: {name}"
