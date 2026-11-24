"""C-02-T41 (TASK-8925; POR-08 a to c, POR-09 e; R-02 C18; DEC-5927).

Row acceptance: "Tess approves the August package on Sep 15 at 8:42 AM in POR-08 and CLS-08 shows
Approved by client, while Ben Ashby sees only Copperleaf's entries." Here, at the module seams:
the `fs_package` kind lists a released package on an engagement scope as well as on its close
(so an entity-wide grant finds it); the client's decline is stored with its reason and sealed
note, the close goes back to review and the releasing partner is told; posted entries of a
non-attest client reach POR-08's posted card as `posted` (read-only), never an attest client's.
The portal service's scope and decider rules (Ben sees only the scopes his grants cover) are
R-02-T11's, exercised in `tests/unit/portal/test_r02t11_approvals_service.py`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from abacus.modules.adjustments import client_approvals as entries
from abacus.modules.closes import release
from abacus.modules.engagements.api import ClientDecision
from abacus.modules.portal import approvals as portal

pytestmark = pytest.mark.asyncio

SEP15_0842 = datetime(2026, 9, 15, 13, 42, tzinfo=UTC)
PRIYA, BEN = uuid4(), uuid4()
_decline_impl = release._decline  # pyright: ignore[reportPrivateUsage]  -- the unit under test
decline = cast(Callable[..., Awaitable[Any]], _decline_impl)  # Any: its loose test shape
_package_item_impl = release._package_item  # pyright: ignore[reportPrivateUsage]  -- the unit under test
package_item = cast(Callable[..., Awaitable[Any]], _package_item_impl)  # Any: its loose test shape
bucket = portal._bucket  # pyright: ignore[reportPrivateUsage]  -- a test double stands in


def _row(**over: object) -> object:
    base: dict[str, object] = {
        "status": "released", "released_by": PRIYA, "released_at": SEP15_0842,
        "client_approved_at": None, "client_declined_at": None, "client_decline_reason": None,
        "content_hash": "a" * 64,
    }  # fmt: skip
    base.update(over)
    return SimpleNamespace(**base)


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None

    def __iter__(self) -> Any:  # noqa: ANN401 -- rows
        return iter(self._rows)


class _Session:
    def __init__(self, rows: list[object], scalars: list[object] | None = None) -> None:
        self.rows = rows
        self.scalars = list(scalars or [])
        self.sql: list[tuple[str, dict[str, object]]] = []

    async def execute(self, statement: object, params: dict[str, object]) -> _Result:
        self.sql.append((str(statement), params))
        return _Result(self.rows)

    async def scalar(self, statement: object, params: dict[str, object]) -> object:
        self.sql.append((str(statement), params))
        return self.scalars.pop(0) if self.scalars else None


async def test_ac_posted_entries_fill_por08s_posted_card() -> None:
    assert bucket("posted") == "posted"
    assert bucket("waiting") == "waiting" and bucket("approved") == "approved"
    sql = str(entries._POSTED_ON_SCOPE)  # pyright: ignore[reportPrivateUsage]  -- a test double stands in
    assert "e.status = 'posted'" in sql and "NOT e.is_attest_client" in sql
    assert entries._STATE["posted"] == "posted"  # pyright: ignore[reportPrivateUsage]  -- a test double stands in


async def test_ac_the_package_reads_waiting_approved_and_declined() -> None:
    close = uuid4()
    waiting = await package_item(_Session([_row()]), close)
    assert (waiting.state, waiting.kind) == ("waiting", "fs_package")
    approved = await package_item(_Session([_row(client_approved_at=SEP15_0842)]), close)
    assert (approved.state, approved.decided_at) == ("approved", SEP15_0842)
    declined = await package_item(
        _Session([_row(status="declined_by_client", client_declined_at=SEP15_0842,
                       client_decline_reason="number_looks_wrong")]),
        close,
    )  # fmt: skip
    assert (declined.state, declined.reason_code) == ("declined", "number_looks_wrong")


async def test_ac_an_entity_grant_finds_the_package_on_its_engagement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close = uuid4()
    session = _Session([SimpleNamespace(close_id=close)])

    class _Ctx:
        async def __aenter__(self) -> _Session:
            return session

        async def __aexit__(self, *_a: object) -> None:
            return None

    async def item(_s: object, i: UUID) -> object:
        return SimpleNamespace(item_id=i)

    monkeypatch.setattr(release, "tenant_session", lambda _t: _Ctx())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]  -- a test double stands in
    monkeypatch.setattr(release, "_package_item", item)
    engagement = uuid4()
    no_tenant = cast(Any, None)  # Any: the stubbed read ignores the tenant
    found = await release.PROVIDER.items(no_tenant, engagement)
    items = cast(list[Any], found)  # Any: the provider's item shape
    assert [f.item_id for f in items] == [close]
    sql, params = session.sql[0]
    assert "c.engagement_id = :s" in sql and params == {"s": engagement}


async def test_ac_a_decline_stores_the_reason_reopens_review_and_tells_the_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.kernel import crypto

    close, tenant = uuid4(), uuid4()
    session = _Session([_row(status="declined_by_client", client_declined_at=SEP15_0842,
                             client_decline_reason="other")],
                       scalars=[tenant, PRIYA])  # fmt: skip
    recorded: list[str] = []
    emitted: list[object] = []

    def record(action: str, **_k: object) -> None:
        recorded.append(action)

    tx = SimpleNamespace(session=session, record=record, emit=emitted.append)
    sealed: list[str] = []

    async def seal(_t: UUID, plaintext: bytes, purpose: str) -> bytes:
        sealed.append(purpose)
        return b"sealed:" + plaintext

    statuses: list[str] = []

    async def close_row(_s: object, _c: UUID, lock: bool = False) -> object:
        return SimpleNamespace(status="delivered", row_version=4)

    async def update_status(_s: object, _c: UUID, **k: object) -> object:
        statuses.append(str(k["status"]))
        return object()

    monkeypatch.setattr(crypto, "seal", seal)
    monkeypatch.setattr(release.repo, "close_row", close_row)
    monkeypatch.setattr(release.repo, "update_status", update_status)
    word = ClientDecision("decline", "a" * 64, "other", "The cash balance is off by $2,000.")
    out = await decline(tx, close, word, BEN)
    update = next(params for sql, params in session.sql if "declined_by_client" in sql)
    assert (update["r"], update["k"]) == ("other", BEN)
    assert update["n"] == b"sealed:The cash balance is off by $2,000."
    assert sealed == ["closes.decline_note"]
    assert statuses == ["in_review"]
    assert recorded == ["close_package.client_declined"]
    event = cast(release.PackageClientDeclined, emitted[0])
    assert (event.recipient_user_ids, event.reason_code) == ([PRIYA], "other")
    assert out.state == "declined"


async def test_a_decided_package_cannot_be_declined(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.engagements.api import ItemChanged

    session = _Session([], scalars=[uuid4(), None])  # the UPDATE matches no waiting package
    tx = SimpleNamespace(session=session, record=lambda *_a, **_k: None, emit=lambda _e: None)  # pyright: ignore[reportUnknownLambdaType]  -- a test double stands in
    with pytest.raises(ItemChanged):
        await decline(tx, uuid4(), ClientDecision("decline", "a" * 64, "something_missing"), BEN)
