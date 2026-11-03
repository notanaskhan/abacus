"""A-06-T15 (TASK-3215; DEC-2215): G5 review complete.

Row acceptance: "G5 reads not met with one blocker for Marcus Delaney's stale L2 and one for
RN-13, and flips to met within one transaction of the last clearing action." The provider reads
only the review module's own facts, so the rule is pinned here with those facts replaced.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from abacus.modules.assurance import gates
from abacus.modules.review.api import Reviewable, ReviewableFacts
from abacus.modules.review.service import LevelState

PAPER = uuid.uuid4()
NOTE = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()


def _state(level: int, *, stale: bool = False, signed: bool = True) -> LevelState:
    return LevelState(
        level, f"L{level}", uuid.uuid4() if signed else None, datetime.now(UTC), stale
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch, states: list[LevelState], notes: list[uuid.UUID]
) -> None:
    async def reviewables(_t: object, _e: uuid.UUID) -> list[Reviewable]:
        return [Reviewable("workpaper", PAPER, "EBP-04", "Contributions", "h" * 64, True)]

    async def facts(_t: object, kind: str, target: uuid.UUID) -> ReviewableFacts:
        return ReviewableFacts(kind, target, ENGAGEMENT, "h" * 64, 3, frozenset(), (1, 2))

    async def sign_offs(
        _t: object, _k: str, ids: list[uuid.UUID], _h: object
    ) -> dict[uuid.UUID, list[LevelState]]:
        return {ids[0]: states}

    async def open_notes(_t: object, _e: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        return [(n, PAPER) for n in notes]

    monkeypatch.setattr(gates, "reviewables_of", reviewables)
    monkeypatch.setattr(gates, "reviewable_facts", facts)
    monkeypatch.setattr(gates, "sign_off_states", sign_offs)
    monkeypatch.setattr(gates, "open_notes", open_notes)


async def test_ac_a_stale_l2_and_an_open_note_are_the_two_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_state(1), _state(2, stale=True)], [NOTE])
    fact = await gates.g5_facts(SimpleNamespace(), ENGAGEMENT)  # type: ignore[arg-type] -- the test reaches past the public type
    assert not fact.met
    assert fact.blockers == (f"stale:workpaper:{PAPER}:L2", f"review_note:{NOTE}")


async def test_ac_met_once_every_level_is_signed_and_no_note_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_state(1), _state(2)], [])
    fact = await gates.g5_facts(SimpleNamespace(), ENGAGEMENT)  # type: ignore[arg-type] -- the test reaches past the public type
    assert fact.met and fact.blockers == ()


async def test_ac_an_unsigned_level_blocks_and_a_failure_never_meets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_state(1)], [])
    fact = await gates.g5_facts(SimpleNamespace(), ENGAGEMENT)  # type: ignore[arg-type] -- the test reaches past the public type
    assert fact.blockers == (f"unsigned:workpaper:{PAPER}:L2",)

    async def broken(_t: object, _e: uuid.UUID) -> list[Reviewable]:
        raise RuntimeError("down")

    monkeypatch.setattr(gates, "reviewables_of", broken)
    fact = await gates.g5_facts(SimpleNamespace(), ENGAGEMENT)  # type: ignore[arg-type] -- the test reaches past the public type
    assert fact == gates.GateFact(met=False, blockers=("review_unavailable",))


def test_ac_assurance_owns_g5() -> None:
    from abacus.modules.assurance import (
        api as _api,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- the test reaches past the public type
    )
    from abacus.modules.engagements import slots

    assert slots._GATES["G5"] is gates.g5_facts  # pyright: ignore[reportPrivateUsage] -- the private helper under test
