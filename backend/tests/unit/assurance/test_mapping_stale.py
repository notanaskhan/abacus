"""A-03-T14 (TASK-5010, TASK-2714; DEC-1765): the mapping follows its trial balance's versions.

Version 1 starts the set on the firm's one published grouping set; a later version is followed
and, when it changed a signed mapping, announced stale once to its signers; nothing happens with
`ledger.tb_mapping` off, with no mapping, or on a replay.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import mapping as m
from abacus.modules.notifications.catalogue import CATALOGUE
from abacus.modules.review.stale import STALE_SOURCES

T = UUID(int=1)
CALEB, HANNAH = UUID(int=21), UUID(int=22)


def _event(version: int, tb: UUID | None = None) -> OutboxEvent:
    return OutboxEvent(
        uuid4(),
        T,
        "trial_balance.version_created",
        {
            "trial_balance_id": str(tb or uuid4()),
            "engagement_id": str(uuid4()),
            "version_no": version,
        },
    )


class _Tx:
    def __init__(self, sink: list[object]) -> None:
        self.sink = sink

    def record(self, *args: object, **kwargs: object) -> None:
        self.sink.append(("audit", args[0]))

    def emit(self, event: object) -> None:
        self.sink.append(event)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mapped: bool,
    stale: bool,
    duplicate: bool = False,
    on: bool = True,
    grouping_sets: int = 1,
) -> list[object]:
    sink: list[object] = []
    ms_id = UUID(int=7)

    async def flag_enabled(*_a: object) -> bool:
        return on

    async def mapping_set_of(_t: object, _tb: UUID) -> object:
        return SimpleNamespace(id=ms_id) if mapped else None

    async def mapping_with_prior(*_a: object) -> object:
        return SimpleNamespace(content_hash="h2", unmapped=1)

    async def stale_of(*_a: object) -> list[object]:
        return [object()] if stale else []

    async def sign_off_states(*_a: object) -> dict[UUID, list[object]]:
        return {
            ms_id: [
                SimpleNamespace(level=1, signed_by=CALEB),
                SimpleNamespace(level=2, signed_by=HANNAH),
                SimpleNamespace(level=3, signed_by=None),
            ]
        }

    async def follow_tb_version(tx: _Tx, *_a: object) -> object:
        tx.record("mapping_set.version_followed")
        return SimpleNamespace(kept_edits=3, dropped_edits=0)

    async def published_versions(_t: object) -> list[object]:
        return [
            SimpleNamespace(
                id=UUID(int=40 + n), set_id=UUID(int=30 + n), set_key=f"s{n}", version=1
            )
            for n in range(grouping_sets)
        ]

    async def version_adopter(*_a: object) -> UUID:
        return CALEB

    async def create_mapping_set(tx: _Tx, **kw: object) -> UUID:
        tx.sink.append(("created", kw["version_id"], kw["user_id"]))
        return ms_id

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        if duplicate:
            raise IntegrityError("dup", None, Exception())
        yield _Tx(sink)

    for name, fake in {
        "flag_enabled": flag_enabled,
        "mapping_set_of": mapping_set_of,
        "mapping_with_prior": mapping_with_prior,
        "stale_of": stale_of,
        "sign_off_states": sign_off_states,
        "follow_tb_version": follow_tb_version,
        "published_versions": published_versions,
        "version_adopter": version_adopter,
        "create_mapping_set": create_mapping_set,
        "uow": uow,
    }.items():
        monkeypatch.setattr(m, name, fake)
    return sink


async def test_a03_t14_a_later_version_is_followed_and_announced_stale_once_to_its_signers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _patch(monkeypatch, mapped=True, stale=True)
    assert await m.on_tb_version(_event(2)) is True
    assert ("audit", "mapping_set.version_followed") in sink
    assert ("audit", "mapping_set.went_stale") in sink
    [stale] = [e for e in sink if isinstance(e, m.MappingSetWentStale)]
    assert (stale.version_no, stale.unmapped) == (2, 1)
    assert stale.event_id == m.went_stale_id(UUID(int=7), 2)
    assert list(stale.recipient_user_ids) == sorted([CALEB, HANNAH])
    [followed] = [e for e in sink if isinstance(e, m.MappingSetFollowedVersion)]
    assert followed.event_id == m.followed_id(UUID(int=7), 2)


async def test_a03_t14_an_unsigned_mapping_is_followed_and_nobody_is_told(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _patch(monkeypatch, mapped=True, stale=False)
    assert await m.on_tb_version(_event(2)) is True
    assert ("audit", "mapping_set.version_followed") in sink
    assert not [e for e in sink if isinstance(e, m.MappingSetWentStale)]


async def test_a03_t14_version_1_starts_the_set_on_the_one_published_grouping_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _patch(monkeypatch, mapped=False, stale=False)
    assert await m.on_tb_version(_event(1)) is True
    assert sink == [("created", UUID(int=40), CALEB)]


@pytest.mark.parametrize("sets", [0, 2])
async def test_a03_t14_version_1_leaves_the_choice_to_a_person_with_none_or_several(
    monkeypatch: pytest.MonkeyPatch, sets: int
) -> None:
    sink = _patch(monkeypatch, mapped=False, stale=False, grouping_sets=sets)
    assert await m.on_tb_version(_event(1)) is False
    assert sink == []


@pytest.mark.parametrize(
    ("version", "mapped", "on"), [(1, True, True), (2, False, True), (2, True, False)]
)
async def test_a03_t14_nothing_changes(
    monkeypatch: pytest.MonkeyPatch, version: int, mapped: bool, on: bool
) -> None:
    sink = _patch(monkeypatch, mapped=mapped, stale=True, on=on)
    assert await m.on_tb_version(_event(version)) is False
    assert sink == []


async def test_a03_t14_a_replay_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, mapped=True, stale=True, duplicate=True)
    assert await m.on_tb_version(_event(3)) is False


async def test_a03_t14_signers_are_told_once_by_the_mapping_kind() -> None:
    kind = CATALOGUE["mapping_set.went_stale"]
    assert kind.kind == "mapping_set_stale"
    payload: dict[str, object] = {"recipient_user_ids": [str(CALEB), str(HANNAH)]}
    assert await kind.recipients(T, payload) == sorted([CALEB, HANNAH])
    stale = CATALOGUE["sign_off.went_stale"]
    signed: dict[str, object] = {"signed_by": str(CALEB), "target_type": "mapping_set"}
    assert await stale.recipients(T, signed) == []
    assert await stale.recipients(T, {**signed, "target_type": "workpaper"}) == [CALEB]


def test_a03_t14_the_ids_are_per_mapping_and_version_and_review_listens() -> None:
    a = UUID(int=9)
    assert m.went_stale_id(a, 2) == m.went_stale_id(a, 2) != m.went_stale_id(a, 3)
    assert m.followed_id(a, 2) != m.went_stale_id(a, 2)
    assert STALE_SOURCES["mapping_set.went_stale"] == ("mapping_set", "mapping_set_id")
    assert "trial_balance.version_created" in m.SUBSCRIPTIONS
