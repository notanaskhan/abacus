"""A-02-T33: `connections.live_ledger` stops a live ledger's pulls at once.

Acceptance: production refuses fake providers at boot, the adapter is registered but dark, and a
staging drill shows the kill switch stopping pulls within one minute. Here, the pull itself: with
the flag off for the firm, a running pull through a networked provider ends `connector_paused`
before any credentials are read or the provider is called; the flag is read past its cache; a
networkless provider (the demo ledger, an upload) is not a live ledger and is not stopped.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.modules.connections import pipeline


class Stop(Exception):
    pass


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"flag": False, "fresh": None, "failed": None, "called": []}
    run = SimpleNamespace(
        raw_fingerprint=None,
        status="running",
        connection_id=uuid.uuid4(),
        client_entity_id=uuid.uuid4(),
        dataset="trial_balance",
        period_start=None,
        period_end=None,
    )
    connection = SimpleNamespace(
        id=run.connection_id,
        status="active",
        client_entity_id=run.client_entity_id,
        provider="qbo",
    )
    state["connection"] = connection

    async def _run(_sys: object) -> object:
        return run

    async def _authorised(_sys: object, _action: str) -> None:
        return None

    @contextlib.asynccontextmanager
    async def session(_tenant: object) -> AsyncIterator[object]:
        yield object()

    async def get_connection(_session: object, _id: object) -> object:
        return connection

    async def flag_enabled(_tenant: object, _flag: object, *, fresh: bool = False) -> bool:
        state["fresh"] = fresh
        return bool(state["flag"])

    async def fail_run(_sys: object, status: str, code: str) -> Exception:
        state["failed"] = (status, code)
        return Stop(code)

    async def credentials_of(_tenant: object, _connection: object) -> None:
        state["called"].append("credentials")
        raise Stop("reached the provider")

    monkeypatch.setattr(pipeline, "_run", _run)
    monkeypatch.setattr(pipeline, "_authorised", _authorised)
    monkeypatch.setattr(pipeline, "tenant_session", session)
    monkeypatch.setattr(pipeline, "get_connection", get_connection)
    monkeypatch.setattr(pipeline, "flag_enabled", flag_enabled)
    monkeypatch.setattr(pipeline, "fail_run", fail_run)
    monkeypatch.setattr(pipeline, "credentials_of", credentials_of)
    return state


SYS: Any = SimpleNamespace(tenant=object(), run_id=uuid.uuid4(), engagement_id=uuid.uuid4())


async def test_the_flag_off_ends_the_pull_paused_before_the_provider(
    world: dict[str, Any],
) -> None:
    with pytest.raises(Stop, match="connector_paused"):
        await pipeline.pull_raw(SYS)
    assert world["failed"] == ("failed", "connector_paused")
    assert world["called"] == []  # no credentials read, nothing sent to the provider
    assert world["fresh"] is True  # read past the flag cache: the switch holds at once


async def test_the_flag_on_lets_the_pull_reach_the_provider(world: dict[str, Any]) -> None:
    world["flag"] = True
    with pytest.raises(Stop, match="reached the provider"):
        await pipeline.pull_raw(SYS)
    assert world["called"] == ["credentials"] and world["failed"] is None


@pytest.mark.parametrize("provider", ["fake", "import"])
async def test_a_networkless_provider_is_not_a_live_ledger(
    world: dict[str, Any], provider: str
) -> None:
    world["connection"].provider = provider
    with pytest.raises(Stop, match="reached the provider"):
        await pipeline.pull_raw(SYS)
    assert world["fresh"] is None  # the switch is not consulted
