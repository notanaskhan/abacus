"""SPEC-313 (TASK-325): note states, matrix row status and the G5 gate, by code."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import gate_fact
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review import matrix as matrix_module
from abacus.modules.review.matrix import blockers_of, row_status
from abacus.modules.review.notes import status_of
from abacus.modules.review.service import states_of
from abacus.modules.review.slots import Reviewable

H = "a" * 64


def _event(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind)


def _signed(level: int, digest: str = H) -> SimpleNamespace:
    return SimpleNamespace(
        level=level, signed_by=uuid4(), created_at=datetime.now(UTC), content_hash=digest
    )


def _paper(code: str = "C-100", has_content: bool = True) -> Reviewable:
    return Reviewable("workpaper", uuid4(), code, "Cash", H, has_content)


def test_ac3_a_notes_state_is_its_newest_event() -> None:
    assert status_of([]) == "open"
    assert status_of([_event("responded")]) == "responded"  # type: ignore[list-item]  # stand-ins
    assert status_of([_event("responded"), _event("cleared")]) == "cleared"  # type: ignore[list-item]  # stand-ins
    assert status_of([_event("cleared"), _event("reopened")]) == "open"  # type: ignore[list-item]  # stand-ins


def test_ac4_row_status_by_code() -> None:
    paper = _paper()
    assert row_status(_paper(has_content=False), states_of([], H), 0) == ("not_started", [1, 2])
    assert row_status(paper, states_of([_signed(1)], H), 0) == ("needs_sign_off", [2])  # type: ignore[list-item]  # stand-ins
    done = states_of([_signed(2), _signed(1)], H)  # type: ignore[list-item]  # stand-ins
    assert row_status(paper, done, 0) == ("complete", [])
    assert row_status(paper, done, 1)[0] == "open_notes"
    assert row_status(paper, states_of([_signed(2), _signed(1)], "b" * 64), 0)[0] == (  # type: ignore[list-item]  # stand-ins
        "changed_after_signoff"
    )


def test_ac5_blockers_name_what_is_missing() -> None:
    paper = _paper()
    assert blockers_of([]) == ["nothing_to_review"]
    assert blockers_of([(paper, states_of([_signed(2), _signed(1)], H), 0)]) == []  # type: ignore[list-item]  # stand-ins
    assert blockers_of([(paper, states_of([_signed(1)], H), 2)]) == [  # type: ignore[list-item]  # stand-ins
        "open_notes:C-100:2",
        "unsigned:C-100:L2",
    ]


async def test_ac5_g5_is_registered_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.review import api as review_api  # importing it registers G5

    assert review_api.ROUTERS

    async def broken(_tenant: TenantContext, _engagement: UUID) -> list[Reviewable]:
        raise RuntimeError

    monkeypatch.setattr(matrix_module, "reviewables_of", broken)
    fact = await gate_fact(TenantContext(uuid4(), "system", "test"), uuid4(), "G5")
    assert (fact.met, fact.blockers) == (False, ("review_unavailable",))


def test_ac2_people_raise_answer_and_clear_notes() -> None:
    for action in ("review_note.raise", "review_note.respond", "review_note.clear"):
        assert RULES[action].decisions.get("agent") != "allow"
