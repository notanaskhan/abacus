"""F-03-T18: a frozen contract's fields can't be removed, renamed or retyped, and its enum
members can't be removed, without shipping the next version. Additions pass."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools import contracts


def test_t18_today_breaks_no_frozen_contract() -> None:
    assert contracts.check() == []


def test_t18_c1_and_c2_are_frozen_at_v1() -> None:
    frozen = contracts.snapshots()
    assert [p.stem for p in frozen["c1_work_items"]] == ["v1"]
    assert [p.stem for p in frozen["c2_status_registry"]] == ["v1"]


FROZEN = {
    "Thing": {
        "properties": {"id": {"type": "string"}, "count": {"type": "integer"}},
        "required": ["id"],
    },
    "ThingStatus": {"enum": ["open", "done"]},
}


@pytest.mark.parametrize(
    ("now", "problem"),
    [
        ({"Thing": {"properties": {"id": {"type": "string"}}, "required": ["id"]}}, "removed"),
        (
            {"Thing": {"properties": {"id": {"type": "integer"}, "count": {"type": "integer"}}}},
            "type changed",
        ),
        (
            {
                "Thing": {
                    "properties": {"id": {"type": "string"}, "count": {"type": "integer"}},
                    "required": ["id", "count"],
                }
            },
            "now required",
        ),
        ({"ThingStatus": {"enum": ["open"]}}, "enum member 'done' removed"),
    ],
)
def test_t18_breaking_changes_are_found(now: dict[str, object], problem: str) -> None:
    current = {**FROZEN, **now}
    assert any(problem in p for p in contracts.breaking(FROZEN, current))  # type: ignore[arg-type]  # test fixtures


def test_t18_additions_pass() -> None:
    now = {
        "Thing": {
            "properties": {
                "id": {"type": "string", "title": "Id"},
                "count": {"type": "integer"},
                "extra": {"type": "boolean"},
            },
            "required": ["id"],
        },
        "ThingStatus": {"enum": ["open", "done", "archived"]},
    }
    assert contracts.breaking(FROZEN, now) == []  # type: ignore[arg-type]  # test fixtures


def test_t18_a_frozen_version_is_never_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "c1_work_items").mkdir()
    (tmp_path / "c1_work_items" / "v1.json").write_text("{}")
    monkeypatch.setattr(contracts, "CONTRACTS", tmp_path)
    with pytest.raises(SystemExit, match="never rewritten"):
        contracts.freeze("c1_work_items", "v1")
