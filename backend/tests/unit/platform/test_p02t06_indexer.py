"""P-02-T06 (TASK-7615; DEC-4612): the SearchIndexer's composition and rules, without a database.

The subscriptions are composed from the registered triggers when read; an event's ids are rebuilt
inline up to `FANOUT` and handed to the reindex workflow above it; `membership.deactivated` purges
that person's recents; a builder answering None deletes the row and a document outside the contract
is not stored; hostile characters are scrubbed; the drift hash is canonical."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.platform.search import indexer, scrub, spec, store

NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
TENANT = uuid4()


def _doc(object_id: UUID, title: str = "Jonah & Claire Feld") -> spec.SearchIndexDocument:
    return spec.SearchIndexDocument(
        object_id=object_id,
        title=title,
        source_updated_at=NOW,
        target_params={"clientId": str(object_id)},
        client_id=object_id,
    )


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> spec.SearchProjection:
    monkeypatch.setattr(spec, "_PROJECTIONS", {})

    async def build(tenant: object, object_id: UUID) -> spec.SearchIndexDocument | None:
        return _doc(object_id)

    projection = spec.SearchProjection(
        object_type="p02_client",
        group="clients",
        read_action="reference_set.read",
        scope_kind="client",
        build=build,
        target="CLI-02",
        triggers={"client.updated": lambda p: [UUID(str(i)) for i in p["ids"]]},  # type: ignore[union-attr]
    )
    spec.register(projection)
    return projection


def _event(event_type: str, payload: dict[str, object]) -> OutboxEvent:
    return OutboxEvent(uuid4(), TENANT, event_type, payload)


def test_subscriptions_compose_the_registered_triggers(registered: spec.SearchProjection) -> None:
    assert set(indexer.SUBSCRIPTIONS) == {"client.updated", "membership.deactivated"}
    assert len(indexer.SUBSCRIPTIONS) == 2


def test_an_event_reindexes_its_ids_inline(
    registered: spec.SearchProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[UUID] = []

    async def upsert(tenant_id: UUID, projection: object, doc: spec.SearchIndexDocument) -> None:
        seen.append(doc.object_id)

    monkeypatch.setattr(store, "upsert", upsert)
    ids = [uuid4(), uuid4()]
    asyncio.run(indexer.SUBSCRIPTIONS["client.updated"](_event("client.updated", {"ids": ids})))
    assert seen == ids


def test_a_fanout_goes_to_the_workflow(
    registered: spec.SearchProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[int] = []

    async def reindex(tenant_id: UUID, object_type: str | None, **kw: object) -> str:
        started.append(len(kw["ids"]))  # type: ignore[arg-type]
        return "run"

    monkeypatch.setattr(indexer, "request_reindex", reindex)
    ids = [uuid4() for _ in range(indexer.FANOUT + 1)]
    asyncio.run(indexer.SUBSCRIPTIONS["client.updated"](_event("client.updated", {"ids": ids})))
    assert started == [indexer.FANOUT + 1]


def test_membership_deactivated_purges_recents(monkeypatch: pytest.MonkeyPatch) -> None:
    purged: list[UUID] = []

    async def purge(tenant_id: UUID, user_ids: list[UUID]) -> int:
        purged.extend(user_ids)
        return 1

    monkeypatch.setattr(store, "purge_recents", purge)
    user = uuid4()
    handler = indexer.SUBSCRIPTIONS["membership.deactivated"]
    asyncio.run(handler(_event("membership.deactivated", {"user_id": str(user)})))
    assert purged == [user]


def test_a_none_builder_deletes_and_a_refused_document_is_not_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spec, "_PROJECTIONS", {})
    deleted: list[UUID] = []
    stored: list[UUID] = []

    async def delete(tenant_id: UUID, object_type: str, object_id: UUID) -> bool:
        deleted.append(object_id)
        return True

    async def upsert(tenant_id: UUID, projection: object, doc: spec.SearchIndexDocument) -> None:
        stored.append(doc.object_id)

    monkeypatch.setattr(store, "delete", delete)
    monkeypatch.setattr(store, "upsert", upsert)
    gone, bad = uuid4(), uuid4()

    async def build(tenant: object, object_id: UUID) -> spec.SearchIndexDocument | None:
        return None if object_id == gone else _doc(object_id, "x" * 301)

    spec.register(
        spec.SearchProjection(
            object_type="p02_probe",
            group="clients",
            read_action="reference_set.read",
            scope_kind="client",
            build=build,
            target="CLI-02",
        )
    )
    assert asyncio.run(indexer.index_object(TENANT, "p02_probe", gone)) == "deleted"
    assert asyncio.run(indexer.index_object(TENANT, "p02_probe", bad)) == "refused"
    assert asyncio.run(indexer.index_object(TENANT, "p02_unknown", bad)) == "unregistered"
    assert deleted == [gone, bad] and stored == []


def test_hostile_characters_are_scrubbed() -> None:
    doc = _doc(uuid4(), "Feld‮ dlroW\u0000  Holdings")
    clean = scrub.scrub_document(doc)
    assert clean.title == "Feld dlroW Holdings"


def test_the_drift_hash_is_canonical(registered: spec.SearchProjection) -> None:
    object_id = uuid4()
    a = store.document_hash(registered, _doc(object_id))
    b = store.document_hash(registered, _doc(object_id))
    assert a == b and len(a) == 64
    assert store.document_hash(registered, _doc(object_id, "Feld Holdings")) != a
