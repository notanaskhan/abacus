"""A-09-T33 rest (S48): POR-23's picker links the person's own drop to one of the room's
deliverables; anything else is 404 and nothing is linked."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.assurance import component_auditors as ca
from abacus.modules.assurance import component_room as room
from abacus.modules.evidence import api as evidence

PERSON, OTHER = uuid.uuid4(), uuid.uuid4()
ENGAGEMENT, AUDITOR, ITEM = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class _Ctx:
    tenant_id = uuid.uuid4()
    tenant = object()
    user_id = PERSON


class _Session:
    def __init__(self, answers: list[object]) -> None:
        self.answers = answers

    async def scalar(self, *_: object) -> object:
        return self.answers.pop(0)


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    upload: evidence.ComponentUpload | None,
    mine: object,
    linked: object,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    received: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def granted(*_: object) -> dict[str, object]:
        return {"engagement_id": ENGAGEMENT, "auditor_id": AUDITOR}

    async def upload_of(*_: object) -> evidence.ComponentUpload | None:
        return upload

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[_Session]:
        yield _Session([mine, linked])

    async def receive(_t: object, deliverable: uuid.UUID, item: uuid.UUID) -> None:
        received.append((deliverable, item))

    monkeypatch.setattr(room, "_granted", granted)
    monkeypatch.setattr(evidence, "component_upload_of", upload_of)
    monkeypatch.setattr(room, "tenant_session", session)
    monkeypatch.setattr(ca, "receive_deliverable", receive)
    return received


async def test_the_persons_own_drop_links_to_the_rooms_deliverable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deliverable = uuid.uuid4()
    received = _wire(monkeypatch, evidence.ComponentUpload(ITEM, ENGAGEMENT, PERSON), 1, None)
    assert await room.link_drop(_Ctx(), uuid.uuid4(), uuid.uuid4(), deliverable) == deliverable  # type: ignore[arg-type] -- only the ids are read
    assert received == [(deliverable, ITEM)]


@pytest.mark.parametrize(
    ("upload", "mine", "linked"),
    [
        (None, 1, None),  # not a component upload (a firm document)
        (evidence.ComponentUpload(ITEM, ENGAGEMENT, OTHER), 1, None),  # someone else's drop
        (evidence.ComponentUpload(ITEM, uuid.uuid4(), PERSON), 1, None),  # another engagement
        (evidence.ComponentUpload(ITEM, ENGAGEMENT, PERSON), None, None),  # another room's
        (evidence.ComponentUpload(ITEM, ENGAGEMENT, PERSON), 1, 1),  # already linked
    ],
)
async def test_anything_else_is_404_and_nothing_links(
    monkeypatch: pytest.MonkeyPatch,
    upload: evidence.ComponentUpload | None,
    mine: object,
    linked: object,
) -> None:
    received = _wire(monkeypatch, upload, mine, linked)
    with pytest.raises(NotFound):
        await room.link_drop(_Ctx(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())  # type: ignore[arg-type] -- only the ids are read
    assert received == []
