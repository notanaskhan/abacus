"""S33 partials round (R-02-T09/T16/T17; DEC-3136): POR-09's live reads over C10. A person reads
only versions C10's reader rule admits; `approve` is offered only on the newest waiting version
and carries the C18 item's `seen_hash`; a withdrawn version is listed without actions."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import deliverable_portal as dp

DELIVERABLE = uuid.uuid4()
ITEM = uuid.uuid4()
AT = datetime(2026, 10, 8, 14, tzinfo=UTC)


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return cast(
        AuthContext,
        SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "human", str(user)), user_id=user),
    )


def _version(
    no: int, *, draft: bool = True, approval: bool = True, withdrawn: bool = False
) -> object:
    return SimpleNamespace(
        version_no=no,
        is_draft=draft,
        page_count=14,
        page_comments=draft,
        render_hash=f"{no:064x}",
        approval_kind="fs_draft" if approval else None,
        approval_item_id=ITEM if approval else None,
        published_at=AT,
        withdrawn_at=AT if withdrawn else None,
    )


class _Rows:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def first(self) -> object | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[object]:
        return self.rows


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    versions: list[object],
    *,
    state: str = "waiting",
    readable: bool = True,
) -> None:
    head = SimpleNamespace(
        id=DELIVERABLE, kind="fs_draft", title="Financial statements", restricted_use=False,
        legend_kind=None,
    )  # fmt: skip

    class Session:
        async def execute(self, sql: object, _p: object) -> _Rows:
            return _Rows([head]) if "FROM deliverables WHERE" in str(sql) else _Rows(versions)

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[Session]:
        yield Session()

    async def reader(_ctx: object, _d: uuid.UUID, _n: int) -> object:
        if not readable:
            raise NotFound("deliverable")
        return object()

    class Provider:
        async def item(self, _t: object, _i: uuid.UUID) -> object:
            return SimpleNamespace(seen_hash="seen-v", sent_to_client=True, state=state)

    monkeypatch.setattr(dp, "tenant_session", session)
    monkeypatch.setattr(dp, "reader_version", reader)
    monkeypatch.setattr(dp, "client_approval_provider", lambda _k: Provider())


async def test_approve_is_offered_only_on_the_newest_waiting_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_version(3), _version(4)])
    found = await dp.portal_deliverable(_ctx(), DELIVERABLE)
    v3, v4 = found.versions
    assert "approve" not in v3.allowed_actions
    assert v4.allowed_actions == ("download", "approve", "comment")
    assert v4.seen_hash == "seen-v"
    assert found.status == "for_your_review"


async def test_an_approved_draft_reads_approved_by_you_and_offers_no_approve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_version(4)], state="approved")
    found = await dp.portal_deliverable(_ctx(), DELIVERABLE)
    assert found.status == "approved_by_you"
    assert "approve" not in found.versions[0].allowed_actions


async def test_a_final_without_approval_hashes_its_render(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [_version(5, draft=False, approval=False)])
    found = await dp.portal_deliverable(_ctx(), DELIVERABLE)
    assert found.status == "final"
    assert found.versions[0].seen_hash == f"{5:064x}"
    assert found.versions[0].allowed_actions == ("download",)


async def test_a_withdrawn_version_is_listed_without_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, [_version(3, withdrawn=True), _version(4)])
    old, new = (await dp.portal_deliverable(_ctx(), DELIVERABLE)).versions
    assert old.allowed_actions == () and old.withdrawn_on == AT.date()
    assert "approve" in new.allowed_actions


async def test_a_person_outside_every_audience_reads_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, [_version(4)], readable=False)
    with pytest.raises(NotFound):
        await dp.portal_deliverable(_ctx(), DELIVERABLE)


async def test_portal_client_ids_follow_the_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    client_a, client_b = uuid.uuid4(), uuid.uuid4()
    g1 = SimpleNamespace(scope_kind="engagement", scope_id=uuid.uuid4())
    g2 = SimpleNamespace(scope_kind="client", scope_id=client_b)

    async def grants(*_a: object) -> list[object]:
        return [g1, g2]

    async def facts(_t: object, kind: str, scope: uuid.UUID) -> object:
        return SimpleNamespace(client_id=client_a if kind == "engagement" else scope)

    monkeypatch.setattr(dp, "active_grants", grants)
    monkeypatch.setattr(dp, "scope_facts", facts)
    assert await dp.portal_client_ids(_ctx()) == [client_a, client_b]
    assert await dp.portal_client_ids(_ctx(), client_b) == [client_b]
    assert await dp.portal_client_ids(_ctx(), uuid.uuid4()) == []
