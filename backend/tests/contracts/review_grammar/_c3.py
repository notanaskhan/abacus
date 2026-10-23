"""Shared reads for the C3 v1 consumer tests (P-04-T09): the OpenAPI document, the status
registry, the contract doc's example payloads and the field-need tables.

The examples are the JSON blocks of `docs/contracts/review-grammar.md` §8, read as the doc wrote
them. Ids there are placeholders (`"<tb>"`); `wire()` swaps each for a stable UUID (and `"<time>"`
for an instant) so the examples validate against the contract models unchanged otherwise.
"""

from __future__ import annotations

import json
import re
import uuid
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import Classification, level_of

Json = dict[str, object]

REPO = Path(__file__).resolve().parents[4]
CONTRACT_DOC = REPO / "docs" / "contracts" / "review-grammar.md"
MIGRATIONS = REPO / "backend" / "migrations" / "versions"

OPENAPI = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], OPENAPI["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, OPENAPI["components"])["schemas"])
REGISTRY = cast(
    dict[str, dict[str, dict[str, dict[str, object]]]],
    yaml.safe_load((REPO / "docs" / "product" / "status-vocabulary.yaml").read_text())["objects"],
)

_DOC = CONTRACT_DOC.read_text()
_BLOCKS: list[Json] = [
    cast(Json, json.loads(b)) for b in re.findall(r"```json\n(.*?)```", _DOC, re.S)
]
_PLACEHOLDER = re.compile(r"^<[a-z0-9-]+>$")
# One instant for `"<time>"` (the SHL-12 b note rows): E0, Mon Sep 14, 2026, 9:41 AM CT.
_E0 = "2026-09-14T14:41:00Z"


def example(*keys: str) -> Json:
    """The one §8 JSON block whose top-level keys include all of `keys`."""
    found = [b for b in _BLOCKS if set(keys) <= set(b)]
    assert len(found) == 1, f"{len(found)} examples carry {keys}"
    return found[0]


def example_where(key: str, value: object) -> Json:
    """The one §8 JSON block whose top-level `key` is `value` (P-04-T12: part 3's two issue
    creates carry the same keys, so they are told apart by a value)."""
    found = [b for b in _BLOCKS if key in b and b[key] == value]
    assert len(found) == 1, f"{len(found)} examples have {key} = {value!r}"
    return found[0]


def inline_example(after: str) -> Json:
    """An inline `{...}` example in the doc's prose, the first after the text `after`."""
    match = re.search(re.escape(after) + r"\s*`(\{.*?\})`", _DOC)
    assert match is not None, f"no inline example after {after!r}"
    return cast(Json, json.loads(match.group(1)))


def _placeholder(value: str) -> str:
    if value == "<time>":
        return _E0
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"brightwater-hale:{value}"))


def wire(value: object) -> object:
    """The example with each placeholder replaced; everything else as written."""
    if isinstance(value, str) and _PLACEHOLDER.match(value):
        return _placeholder(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in cast(Json, value).items()}
    if isinstance(value, list):
        return [wire(v) for v in cast(list[object], value)]
    return value


def keys(value: object) -> object:
    """The key tree of a JSON value: dicts by key, lists by position, leaves as None."""
    if isinstance(value, dict):
        return {k: keys(v) for k, v in cast(Json, value).items()}
    if isinstance(value, list):
        return [keys(v) for v in cast(list[object], value)]
    return None


def conforms[M: BaseModel](model: type[M], body: Json) -> M:
    """`body` validates as `model`, and carries exactly the model's fields at every level (an
    `Out` model ignores extra keys, so a renamed field would otherwise pass silently)."""
    parsed = model.model_validate(wire(body))
    assert keys(parsed.model_dump(mode="json")) == keys(body)
    return parsed


def level(model: type[BaseModel], field: str) -> Classification | None:
    return level_of(model.model_fields[field])


def restricted_anywhere(model: type[BaseModel], seen: frozenset[type] = frozenset()) -> list[str]:
    """Dotted names of Restricted fields in `model` and every model nested in it."""
    found: list[str] = []
    for name, info in model.model_fields.items():
        if level_of(info) == "restricted":
            found.append(name)
        for inner in _models_in(info.annotation):
            if inner not in seen:
                found += [f"{name}.{n}" for n in restricted_anywhere(inner, seen | {model})]
    return found


def _models_in(annotation: object) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    args = cast(tuple[object, ...], getattr(cast(object, annotation), "__args__", ()))
    return [m for arg in args for m in _models_in(arg)]


def stored_codes(registry_object: str) -> list[str]:
    codes = REGISTRY[registry_object]["codes"]
    return [c for c, facts in codes.items() if not facts["derived"]]


def schema_ref(schema: str, field: str) -> object:
    props = cast(dict[str, Json], SCHEMAS[schema]["properties"])
    return props[field].get("$ref")


def migration(name: str) -> str:
    return (MIGRATIONS / name).read_text()


def check_list(sql: str, column: str, table: str) -> list[str]:
    """The `column IN (...)` CHECK values of `CREATE TABLE table`, in order."""
    body = re.search(rf"CREATE TABLE {table} \((.*?)\n        \)", sql, re.S)
    assert body is not None, f"no CREATE TABLE {table}"
    found = re.search(rf"CHECK \({column} IN\s*\((.*?)\)\)", body.group(1), re.S)
    assert found is not None, f"no {column} CHECK on {table}"
    return re.findall(r"'([a-z_]+)'", found.group(1))


# --- Figures: Decimal only, never floats (ADR-050) ---------------------------------------------


def dec(text: str) -> Decimal:
    """A doc figure as written ("$16,812,400", "252200", "14,900.00") as an exact Decimal."""
    return Decimal(text.replace("$", "").replace(",", ""))


def round_to(amount: Decimal, increment: Decimal) -> Decimal:
    """Nearest multiple of `increment`, halves up: the materiality rounding of the scenario golden
    (backend/tests/golden/scenario/test_brightwater_hale_golden.py, A-04 AC3.1)."""
    return (amount / increment).quantize(Decimal(1), rounding=ROUND_HALF_UP) * increment
