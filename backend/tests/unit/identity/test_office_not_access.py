"""F-03-T23: "a test proves office is never an access predicate" (chapter 03 §4.2, Q-21: an office
is a filter, never an access boundary). Nothing that decides access — the authorisation package,
`visible()`, the permission matrix's conditions — reads an office."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
AUTHZ = BACKEND / "src" / "abacus" / "modules" / "identity" / "authz"
MATRIX = BACKEND.parent / "docs" / "architecture" / "permission-matrix"
OFFICE = re.compile(r"office", re.IGNORECASE)


def test_the_authorisation_package_never_reads_an_office() -> None:
    hits = [
        f"{path.relative_to(BACKEND)}:{n}"
        for path in sorted(AUTHZ.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if OFFICE.search(line)
    ]
    assert hits == []


def test_no_matrix_rule_or_condition_names_an_office() -> None:
    for path in sorted(MATRIX.glob("*.yaml")):
        document = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        rules = cast(dict[str, dict[str, object] | None], document.get("actions") or {})
        for action, rule in rules.items():
            assert not OFFICE.search(action), (path.name, action)
            for key, value in (rule or {}).items():
                assert not OFFICE.search(key), (path.name, action, key)
                assert not OFFICE.search(str(value)), (path.name, action, value)


def test_visible_never_filters_by_office() -> None:
    source = (AUTHZ / "__init__.py").read_text(encoding="utf-8")
    start = source.index("def visible")
    end = source.find("\ndef ", start + 1)
    body = source[start : end if end != -1 else None]
    assert not OFFICE.search(body)
