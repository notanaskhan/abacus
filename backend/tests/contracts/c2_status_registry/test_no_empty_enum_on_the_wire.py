"""T-04-T07 remainder (DEC-3031): a derived-only status object generates an empty `StrEnum`
(`_statuses.py` keeps only stored codes), so a contract field typed with it accepts no value at
all. Every enum the API publishes names at least one value; a derived status is typed with its
vocabulary codes as a `Literal` instead (as HOME-02's `due_risk`)."""

from __future__ import annotations

from typing import cast

from abacus.api.app import create_app


def _empty_enums(node: object, path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        mapping = cast("dict[str, object]", node)
        if mapping.get("enum") == []:
            out.append(f"{path} ({mapping.get('title', '?')})")
        for key, value in mapping.items():
            _empty_enums(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for i, value in enumerate(cast("list[object]", node)):
            _empty_enums(value, f"{path}[{i}]", out)


def test_every_published_enum_names_a_value() -> None:
    found: list[str] = []
    _empty_enums(create_app().openapi(), "openapi", found)
    assert found == []
