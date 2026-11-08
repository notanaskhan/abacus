"""A-06-T24 partial (TASK-3394, DEC-2393): AUD-17's thread offers Reopen on a cleared note to the
raiser or the engagement partner (SPEC-313 AC-3), and the detail says when the note's paper changed
after a sign-off, for the amber notice."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.review import notes
from abacus.modules.review.models import ReviewableNote
from abacus.modules.review.service import LevelState
from abacus.modules.review.slots import ReviewableFacts, UnregisteredKind

TENANT = uuid4()
ME = uuid4()
OTHER = uuid4()


def _ctx(user: UUID = ME) -> AuthContext:
    return AuthContext(
        TenantContext(TENANT, "human", str(user)), user, uuid4(), None, datetime.now(UTC)
    )


def _note(status: str, raised_by: UUID = ME) -> ReviewableNote:
    return ReviewableNote(
        id=uuid4(),
        tenant_id=TENANT,
        engagement_id=uuid4(),
        target_type="workpaper",
        target_id=uuid4(),
        anchor="EBP-04!K18",
        body=None,
        raised_by=raised_by,
        status=status,
        assignee_user_id=None,
        anchor_ref=None,
    )


ALL = notes._Abilities(respond=True, clear=True, withdraw=True, partner=False)  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_ac_the_raiser_may_reopen_a_cleared_note() -> None:
    assert notes._allowed(_ctx(), _note("cleared"), ALL) == ["review_note.reopen"]  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_ac_the_partner_may_reopen_anyones_cleared_note() -> None:
    partner = notes._Abilities(respond=True, clear=True, withdraw=True, partner=True)  # pyright: ignore[reportPrivateUsage] -- the unit under test
    note = _note("cleared", raised_by=OTHER)
    assert notes._allowed(_ctx(), note, partner) == ["review_note.reopen"]  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_ac_nobody_else_may_reopen_and_an_open_note_has_no_reopen() -> None:
    assert notes._allowed(_ctx(), _note("cleared", raised_by=OTHER), ALL) == []  # pyright: ignore[reportPrivateUsage] -- the unit under test
    cannot = notes._Abilities(respond=True, clear=False, withdraw=True, partner=True)  # pyright: ignore[reportPrivateUsage] -- the unit under test
    assert notes._allowed(_ctx(), _note("cleared"), cannot) == []  # pyright: ignore[reportPrivateUsage] -- the unit under test
    for status in ("open", "responded", "withdrawn", "closed"):
        assert "review_note.reopen" not in notes._allowed(_ctx(), _note(status), ALL)  # pyright: ignore[reportPrivateUsage] -- the unit under test


def _level(level: int, *, signed: bool, stale: bool) -> LevelState:
    return LevelState(level, f"L{level}", uuid4() if signed else None, None, stale)


@pytest.mark.parametrize(
    ("states", "changed"),
    [
        ([_level(1, signed=True, stale=False), _level(2, signed=True, stale=True)], True),
        ([_level(1, signed=True, stale=False), _level(2, signed=False, stale=False)], False),
        ([], False),
    ],
)
async def test_ac_the_detail_says_whether_the_paper_changed_after_a_sign_off(
    monkeypatch: pytest.MonkeyPatch, states: list[LevelState], changed: bool
) -> None:
    note = _note("responded")
    seen: dict[str, object] = {}

    async def facts(_tenant: object, target_type: str, target_id: UUID) -> ReviewableFacts:
        return ReviewableFacts(target_type, target_id, note.engagement_id, "h2", 3, frozenset())

    async def sign_offs(
        _tenant: object, target_type: str, ids: list[UUID], hashes: dict[UUID, str]
    ) -> dict[UUID, list[LevelState]]:
        seen["hashes"] = hashes
        return {i: states for i in ids}

    monkeypatch.setattr(notes, "reviewable_facts", facts)
    monkeypatch.setattr(notes, "sign_off_states", sign_offs)
    assert await notes._paper_changed(_ctx().tenant, note) is changed  # pyright: ignore[reportPrivateUsage] -- the unit under test
    assert seen["hashes"] == {note.target_id: "h2"}


@pytest.mark.parametrize("refused", [UnregisteredKind, NotFound])
async def test_ac_a_paper_whose_owner_cant_say_reads_as_not_changed(
    monkeypatch: pytest.MonkeyPatch, refused: type[Exception]
) -> None:
    async def facts(*_a: object) -> ReviewableFacts:
        raise refused() if refused is UnregisteredKind else refused("workpaper")

    monkeypatch.setattr(notes, "reviewable_facts", facts)
    assert await notes._paper_changed(_ctx().tenant, _note("open")) is False  # pyright: ignore[reportPrivateUsage] -- the unit under test
