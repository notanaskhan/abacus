"""Independent AC tests for G5, the review extensions and the agent seams (A-06-T21; ADR-078;
A-06 §3 F5; I-GATES).

Written apart from A-06-T15 and T23: G5 is met only when every required level is signed on the
current content and no review note is open; a stale sign-off reopens it and a reopened note blocks
it again; a provider failure leaves it unmet; only a person clears a note or resolves a suggestion;
the sign-off matrix is a read (its L5 column carries no action).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
import yaml

from abacus.api.export_openapi import document
from abacus.modules.assurance import findings_contract, gates
from abacus.modules.engagements.api import GateFact

ROOT = Path(__file__).resolve().parents[4]
WP = uuid4()


def _matrix(name: str) -> dict[str, dict[str, str]]:
    return cast(
        dict[str, dict[str, str]],
        yaml.safe_load((ROOT / f"docs/architecture/permission-matrix/{name}.yaml").read_text())[
            "actions"
        ],
    )


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    signed: dict[int, bool],
    stale: frozenset[int] = frozenset(),
    notes: list[tuple[Any, Any]] | None = None,  # Any: test doubles and JSON
    reviewables: bool = True,
) -> None:
    async def reviewables_of(*_a: object) -> list[Any]:  # Any: test doubles and JSON
        return [SimpleNamespace(target_type="workpaper", target_id=WP)] if reviewables else []

    async def reviewable_facts(*_a: object) -> SimpleNamespace:
        return SimpleNamespace(content_hash="h", required_levels=sorted(signed))

    async def sign_off_states(*_a: object) -> dict[Any, list[Any]]:  # Any: test doubles and JSON
        return {
            WP: [
                SimpleNamespace(level=level, signed_by="u" if ok else None, stale=level in stale)
                for level, ok in signed.items()
            ]
        }

    async def open_notes(*_a: object) -> list[tuple[Any, Any]]:  # Any: test doubles and JSON
        return notes or []

    monkeypatch.setattr(gates, "reviewables_of", reviewables_of)
    monkeypatch.setattr(gates, "reviewable_facts", reviewable_facts)
    monkeypatch.setattr(gates, "sign_off_states", sign_off_states)
    monkeypatch.setattr(gates, "open_notes", open_notes)


def _g5() -> GateFact:
    return asyncio.run(gates.g5_facts(cast(Any, None), uuid4()))  # Any: test doubles and JSON


def test_g5_is_met_when_every_required_level_is_signed_and_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, signed={1: True, 2: True, 4: True})
    assert _g5().met is True


def test_staleness_reopens_g5(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, signed={1: True, 2: True}, stale=frozenset({2}))
    fact = _g5()
    assert fact.met is False
    assert fact.blockers == (f"stale:workpaper:{WP}:L2",)


def test_a_reopened_note_blocks_again(monkeypatch: pytest.MonkeyPatch) -> None:
    note = uuid4()
    _wire(monkeypatch, signed={1: True}, notes=[(note, "open")])
    assert _g5().blockers == (f"review_note:{note}",)


def test_an_unsigned_level_and_no_reviewables_leave_g5_unmet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, signed={1: True, 4: False})
    assert _g5().blockers == (f"unsigned:workpaper:{WP}:L4",)
    _wire(monkeypatch, signed={}, reviewables=False)
    assert _g5().blockers == ("no_reviewables",)


def test_a_failing_provider_leaves_g5_unmet_never_met(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(*_a: object) -> list[Any]:  # Any: test doubles and JSON
        raise RuntimeError("review down")

    monkeypatch.setattr(gates, "reviewables_of", broken)
    fact = _g5()
    assert (fact.met, fact.blockers) == (False, ("review_unavailable",))


@pytest.mark.parametrize(
    ("module", "action"),
    [
        ("review", "review_note.clear"),
        ("review", "sign_off.create"),
        ("agents", "suggestion.resolve"),
    ],
)
def test_only_a_person_clears_signs_or_applies_a_suggestion(module: str, action: str) -> None:
    assert _matrix(module)[action]["agent"] == "deny"


def test_the_sign_off_matrix_is_a_read_and_its_cells_carry_no_action() -> None:
    paths = json.loads(document())["paths"]
    assert set(paths["/v1/work-items/{work_item_id}/sign-off-matrix"]) == {"get"}
    assert "allowed_actions" not in findings_contract.SignOffMatrixCellOut.model_fields
