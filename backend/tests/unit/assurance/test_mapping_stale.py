"""A-03-T14 (TASK-5010): a newer trial balance version announces a signed mapping's staleness
once; version 1, no mapping and an unsigned mapping announce nothing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance import mapping as m
from abacus.modules.review.stale import STALE_SOURCES

T = UUID(int=1)


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
    monkeypatch: pytest.MonkeyPatch, *, mapped: bool, stale: bool, duplicate: bool = False
) -> list[object]:
    sink: list[object] = []
    ms_id = UUID(int=7)

    async def mapping_set_of(_t: object, _tb: UUID) -> object:
        return SimpleNamespace(id=ms_id) if mapped else None

    async def mapping_with_prior(*_a: object) -> object:
        return SimpleNamespace(content_hash="h2", unmapped=1)

    async def stale_of(*_a: object) -> list[object]:
        return [object()] if stale else []

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        if duplicate:
            raise IntegrityError("dup", None, Exception())
        yield _Tx(sink)

    monkeypatch.setattr(m, "mapping_set_of", mapping_set_of)
    monkeypatch.setattr(m, "mapping_with_prior", mapping_with_prior)
    monkeypatch.setattr(m, "stale_of", stale_of)
    monkeypatch.setattr(m, "uow", uow)
    return sink


async def test_a03_t14_a_later_version_announces_a_signed_mapping_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _patch(monkeypatch, mapped=True, stale=True)
    assert await m.on_tb_version(_event(2)) is True
    assert ("audit", "mapping_set.went_stale") in sink
    emitted = [e for e in sink if isinstance(e, m.MappingSetWentStale)]
    assert len(emitted) == 1 and emitted[0].version_no == 2
    assert emitted[0].event_id == m.went_stale_id(UUID(int=7), 2)


@pytest.mark.parametrize(
    ("version", "mapped", "stale"), [(1, True, True), (2, False, True), (2, True, False)]
)
async def test_a03_t14_nothing_to_announce(
    monkeypatch: pytest.MonkeyPatch, version: int, mapped: bool, stale: bool
) -> None:
    sink = _patch(monkeypatch, mapped=mapped, stale=stale)
    assert await m.on_tb_version(_event(version)) is False
    assert sink == []


async def test_a03_t14_a_replay_announces_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, mapped=True, stale=True, duplicate=True)
    assert await m.on_tb_version(_event(3)) is False


def test_a03_t14_the_id_is_per_mapping_and_version_and_review_listens() -> None:
    a = UUID(int=9)
    assert m.went_stale_id(a, 2) == m.went_stale_id(a, 2) != m.went_stale_id(a, 3)
    assert STALE_SOURCES["mapping_set.went_stale"] == ("mapping_set", "mapping_set_id")
    assert "trial_balance.version_created" in m.SUBSCRIPTIONS
