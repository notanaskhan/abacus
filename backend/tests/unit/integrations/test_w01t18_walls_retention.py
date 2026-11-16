"""W-01-T18 (TASK-8358; ADR-078): the row's other properties, written outside the implementing
sessions. ac-test-author: ayushkbhatia

- Client-company walls (SPEC-659 AC-17 to AC-19; ADR-026): WB-11 d's list leaves out a client
  the viewer is walled off from; it is neither named nor counted, and a search cannot find it.
- Retention registration (SPEC-659 P-14): `integration_event` is a record class the retention
  service knows, so its years are content like every other's.
- Fake-adapter refusal and membership-end revocation are covered by W-01-T09's conformance tests
  and W-01-T08's AC-13 test against Postgres.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.modules.connections import provider_companies as pc
from abacus.modules.evidence.retention import RECORD_TYPES
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations import api as orgs
from abacus.modules.organisations.service import ClientNames

OPEN, WALLED = uuid.uuid4(), uuid.uuid4()  # client ids
E_OPEN, E_WALLED = uuid.uuid4(), uuid.uuid4()  # their entities
TESS = uuid.uuid4()
AT = datetime(2026, 9, 1, tzinfo=UTC)


class _Rows:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self._rows


class _Session:
    async def execute(self, *_: object, **__: object) -> _Rows:
        return _Rows(
            [
                (uuid.uuid4(), E_WALLED, TESS, AT, AT, "connected"),
                (uuid.uuid4(), E_OPEN, TESS, AT, AT, "needs_reauth"),
            ]
        )


@asynccontextmanager
async def _session(_tenant: object) -> AsyncGenerator[_Session]:
    yield _Session()


@pytest.fixture
def walled(monkeypatch: pytest.MonkeyPatch) -> None:
    async def names(_s: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, ClientNames]:
        known = {
            E_OPEN: ClientNames("Summit Trail", "Summit Trail Outfitters", OPEN),
            E_WALLED: ClientNames("Walled Co", "Walled Co LLC", WALLED),
        }
        return {i: known[i] for i in ids if i in known}

    async def hidden(_t: object, _u: object, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return {i for i in ids if i == WALLED}

    async def people(ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return dict.fromkeys(ids, "Tess Moreno")

    monkeypatch.setattr(pc, "tenant_session", _session)
    monkeypatch.setattr(orgs, "client_names", names)
    monkeypatch.setattr(pc, "hidden_clients", hidden)
    monkeypatch.setattr(pc, "names_of", people)


def _ctx() -> AuthContext:
    # Only tenant and user_id are read.
    return cast(AuthContext, type("Ctx", (), {"tenant": object(), "user_id": uuid.uuid4()})())


@pytest.mark.usefixtures("walled")
async def test_a_walled_client_is_neither_named_nor_counted() -> None:
    found, following = await pc.client_companies(_ctx(), "karbon")
    assert [c.client_name for c in found] == ["Summit Trail Outfitters"]
    assert found[0].connected_by_label == "Tess Moreno (client)"
    assert found[0].ok is False  # needs reauth
    assert following is None


@pytest.mark.usefixtures("walled")
async def test_a_search_cannot_find_a_walled_client() -> None:
    found, _ = await pc.client_companies(_ctx(), "karbon", q="walled")
    assert found == []


def test_integration_events_are_a_retention_record_class() -> None:
    assert "integration_event" in RECORD_TYPES
