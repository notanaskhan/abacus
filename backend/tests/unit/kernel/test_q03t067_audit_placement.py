"""Q-03-T067: where an audit event sits (G-02-T08; SPEC-349 §4, §7; DEC-458), from the contract
in `kernel.uow.placement`.

- With an engagement, the engagement decides: its client (an explicit client must agree) and the
  office of its work item, else its own; an explicit office is ignored; not found, or no placer in
  the process, stores nothing (security review L2, L3).
- With a client target, the target is the client (an explicit client must agree).
- A client with no office takes the client's primary office (DEC-415 Q9); an office already
  known is kept.
- One query per placer for the whole batch; one placer of each kind per process.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, cast

import pytest

from abacus.kernel.uow import placement as subject
from abacus.kernel.uow.placement import EngagementKey, Placeable, Placement

CONN = cast(Any, object())
E1, E2, W1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
CLIENT, OTHER_CLIENT = uuid.uuid4(), uuid.uuid4()
OFFICE, PRIMARY, EXPLICIT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class Placers:
    def __init__(self) -> None:
        self.engagement_calls: list[list[EngagementKey]] = []
        self.client_calls: list[list[uuid.UUID]] = []
        self.engagements: dict[EngagementKey, Placement] = {}
        self.primary: dict[uuid.UUID, uuid.UUID | None] = {}

    async def engagement(
        self, _conn: object, keys: Sequence[EngagementKey]
    ) -> Mapping[EngagementKey, Placement]:
        self.engagement_calls.append(list(keys))
        return {k: v for k, v in self.engagements.items() if k in keys}

    async def client(
        self, _conn: object, clients: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, uuid.UUID | None]:
        self.client_calls.append(list(clients))
        return {c: self.primary.get(c) for c in clients}


@pytest.fixture
def placers(monkeypatch: pytest.MonkeyPatch) -> Iterator[Placers]:
    found = Placers()
    monkeypatch.setattr(subject, "_engagement", [found.engagement])
    monkeypatch.setattr(subject, "_client", [found.client])
    yield found


def _event(
    engagement: uuid.UUID | None = None,
    work_item: uuid.UUID | None = None,
    *,
    target: uuid.UUID | None = None,
    client: uuid.UUID | None = None,
    office: uuid.UUID | None = None,
) -> Placeable:
    return Placeable(engagement, work_item, target, client, office)


async def test_the_engagement_decides_and_an_explicit_office_is_ignored(placers: Placers) -> None:
    placers.engagements[(E1, W1)] = Placement(CLIENT, OFFICE)
    placed = await subject.place(CONN, [_event(E1, W1, client=CLIENT, office=EXPLICIT)])
    assert placed == [Placement(CLIENT, OFFICE)]


async def test_an_explicit_client_that_disagrees_with_the_engagement_is_refused(
    placers: Placers,
) -> None:
    placers.engagements[(E1, None)] = Placement(CLIENT, OFFICE)
    with pytest.raises(subject.PlacementMismatch):
        await subject.place(CONN, [_event(E1, client=OTHER_CLIENT)])


async def test_an_engagement_not_found_stores_nothing(placers: Placers) -> None:
    placers.engagements[(E2, None)] = Placement(None, OFFICE)  # found, but with no client
    placed = await subject.place(
        CONN, [_event(E1, client=CLIENT, office=EXPLICIT), _event(E2, office=EXPLICIT)]
    )
    assert placed == [Placement(None, None), Placement(None, None)]
    assert placers.client_calls == []


async def test_without_an_engagement_placer_nothing_is_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "_engagement", [])
    monkeypatch.setattr(subject, "_client", [])
    placed = await subject.place(CONN, [_event(E1, client=CLIENT, office=EXPLICIT)])
    assert placed == [Placement(None, None)]


async def test_a_client_target_is_the_client_and_must_agree(placers: Placers) -> None:
    placers.primary[CLIENT] = PRIMARY
    assert await subject.place(CONN, [_event(target=CLIENT)]) == [Placement(CLIENT, PRIMARY)]
    with pytest.raises(subject.PlacementMismatch):
        await subject.place(CONN, [_event(target=CLIENT, client=OTHER_CLIENT)])


async def test_a_client_with_no_office_takes_its_primary_and_a_known_office_stays(
    placers: Placers,
) -> None:
    placers.primary[CLIENT] = PRIMARY
    placers.engagements[(E1, None)] = Placement(CLIENT, None)
    placed = await subject.place(
        CONN,
        [
            _event(E1),
            _event(client=CLIENT, office=EXPLICIT),
            _event(client=CLIENT),
            _event(),
        ],
    )
    assert placed == [
        Placement(CLIENT, PRIMARY),
        Placement(CLIENT, EXPLICIT),
        Placement(CLIENT, PRIMARY),
        Placement(None, None),
    ]


async def test_one_query_per_placer_for_the_whole_batch(placers: Placers) -> None:
    placers.engagements[(E1, None)] = Placement(CLIENT, None)
    placers.engagements[(E1, W1)] = Placement(CLIENT, OFFICE)
    placers.primary[CLIENT] = PRIMARY
    await subject.place(CONN, [_event(E1), _event(E1, W1), _event(E1), _event(client=CLIENT)])
    assert len(placers.engagement_calls) == 1
    assert sorted(placers.engagement_calls[0], key=str) == sorted([(E1, None), (E1, W1)], key=str)
    assert placers.client_calls == [[CLIENT]]


async def test_nothing_to_place_asks_no_placer(placers: Placers) -> None:
    assert await subject.place(CONN, [_event(office=EXPLICIT)]) == [Placement(None, EXPLICIT)]
    assert (placers.engagement_calls, placers.client_calls) == ([], [])


def test_one_placer_of_each_kind_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subject, "_engagement", [])
    monkeypatch.setattr(subject, "_client", [])
    first, second = Placers(), Placers()
    engagement, client = first.engagement, first.client  # one object each (a bound method is new)
    subject.register_engagement_placer(engagement)
    subject.register_engagement_placer(engagement)  # the same one again is fine
    with pytest.raises(ValueError):
        subject.register_engagement_placer(second.engagement)
    subject.register_client_placer(client)
    subject.register_client_placer(client)
    with pytest.raises(ValueError):
        subject.register_client_placer(second.client)
