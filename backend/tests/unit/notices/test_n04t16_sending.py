"""N-04-T16 (TASK-3312; DEC-2311): readiness, the follow-up date and the alert plan, from the row.

"On staging the Whitley response reaches Ready to send only after both signatures and an accepted
confirmation, mark-sent on Sep 17 schedules Nov 16, and no route ever calls an irs.gov host." The
database half lands at the integration pass; the staging clause waits for a staging run.
"""

from __future__ import annotations

import ast
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import OutboxEvent
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import sending
from abacus.modules.notices.response_workflow import ALERTS, CP3219A_ALERTS, alert_days
from abacus.modules.notices.sending import follow_up_on, readiness_of

_WHITLEY_PAYMENT = {"required": True, "confirmation_accepted": False}


def test_ac_mark_sent_on_sep_17_schedules_nov_16() -> None:
    assert follow_up_on(date(2026, 9, 17), 60) == date(2026, 11, 16)


def test_ac_ready_only_after_signatures_and_an_accepted_confirmation() -> None:
    assert readiness_of(False, _WHITLEY_PAYMENT, []).blocking == ("envelope", "payment")
    assert readiness_of(True, _WHITLEY_PAYMENT, []).blocking == ("payment",)
    accepted = {"required": True, "confirmation_accepted": True}
    assert readiness_of(False, accepted, []).blocking == ("envelope",)
    assert readiness_of(True, accepted, []).ready


def test_ac_no_payment_needs_no_confirmation() -> None:
    assert readiness_of(True, None, []).ready


def test_ac_a_missing_enclosure_blocks() -> None:
    assert readiness_of(True, None, [{"key": "1099-int"}]).blocking == ("enclosures",)
    assert readiness_of(True, None, [{"key": "1099-int", "included": False}]).ready
    assert readiness_of(True, None, [{"key": "a", "evidence_version_id": "x"}]).ready


def test_ac_r07_a_notice_is_never_ready_unsigned_whatever_else_holds() -> None:
    for payment in (None, {"required": False}, {"required": True, "confirmation_accepted": True}):
        assert not readiness_of(False, payment, []).ready


def test_ac_alert_days_by_notice() -> None:
    assert alert_days("cp2000") == ALERTS == (7, 2)
    assert alert_days("cp3219a") == CP3219A_ALERTS == (30, 14, 7, 2)


def test_ac_no_route_ever_calls_an_irs_host() -> None:
    source = Path(sending.__file__).read_text()
    assert "irs.gov" not in source.lower()
    tree = ast.parse(source)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not imports & {"httpx", "requests", "aiohttp", "urllib"}


async def test_ac_an_agency_reply_cites_only_its_own_engagements_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence column has no key: another engagement's version is refused as absent."""
    ctx = SimpleNamespace(tenant=object(), tenant_id=uuid4(), user_id=uuid4())
    found = SimpleNamespace(engagement_id=uuid4())

    async def _notice(*_: object) -> object:
        return found

    async def _view(*_: object) -> object:
        return SimpleNamespace(engagement_id=uuid4())

    monkeypatch.setattr(sending, "notice", _notice)
    monkeypatch.setattr(sending, "version_view", _view)
    with pytest.raises(NotFound):
        await sending.agency_reply(
            cast(AuthContext, ctx),
            uuid4(),
            outcome="resolved",
            closed_on=None,
            note=None,
            evidence_version_id=uuid4(),
        )


def test_ac_a_payment_due_waits_for_the_accepted_confirmation_then_is_ready() -> None:
    due = {"required": True, sending.CONFIRMATION_ITEM: "x"}
    assert not readiness_of(True, due, []).ready
    assert readiness_of(True, {**due, "confirmation_accepted": True}, []).ready


async def test_ac_a_payment_gets_one_confirmation_request_and_none_without_a_payment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_id = uuid4()
    made: list[object] = []

    async def add(_ctx: object, _engagement: object, new: object) -> SimpleNamespace:
        made.append(new)
        return SimpleNamespace(id=item_id)

    monkeypatch.setattr(sending, "add_request_item", add)
    ctx = cast(AuthContext, SimpleNamespace())
    helper = sending._with_confirmation_request  # pyright: ignore[reportPrivateUsage] -- own helper
    assert await helper(ctx, uuid4(), None) is None
    assert await helper(ctx, uuid4(), {"required": False}) == {"required": False}
    once = await helper(ctx, uuid4(), {"required": True})
    assert once == {"required": True, sending.CONFIRMATION_ITEM: str(item_id)}
    assert await helper(ctx, uuid4(), once) == once
    assert len(made) == 1


@pytest.mark.parametrize(("status", "publishes"), [("accepted", True), ("uploaded", False)])
async def test_ac_staff_accepting_the_confirmation_moves_the_band_once(
    monkeypatch: pytest.MonkeyPatch, status: str, publishes: bool
) -> None:
    """US-7.2: only an accepted upload marks the payment, and only a signed letter publishes."""
    item = uuid4()
    row: dict[str, object] = {
        "id": uuid4(),
        "work_item_id": uuid4(),
        "payment": {"required": True, sending.CONFIRMATION_ITEM: str(item)},
        "enclosures": [],
        "envelope_id": uuid4(),
    }
    published: list[bool] = []
    written: list[dict[str, object]] = []

    class _Session:
        async def execute(self, _sql: object, params: dict[str, object] | None = None) -> object:
            if params and "p" in params:
                written.append(params)
            rows = cast("list[object]", [row])
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))

    @asynccontextmanager
    async def session(_tenant: object) -> AsyncGenerator[_Session]:
        yield _Session()

    @asynccontextmanager
    async def unit(_tenant: object) -> AsyncGenerator[SimpleNamespace]:
        def record(*_a: object, **_k: object) -> None:
            return None

        yield SimpleNamespace(session=_Session(), record=record)

    async def items(_tenant: object, _version: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=item, status=status)]

    async def envelope(_tenant: object, _id: object) -> str:
        return "completed"

    async def publish(_tenant: object, _row: object, *, signed: bool) -> None:
        published.append(signed)

    async def on_day(_tenant: object) -> date:
        return date(2026, 9, 16)

    monkeypatch.setattr(sending, "today", on_day)
    monkeypatch.setattr(sending, "items_of_version", items)
    monkeypatch.setattr(sending, "tenant_session", session)
    monkeypatch.setattr(sending, "uow", unit)
    monkeypatch.setattr(sending, "envelope_status", envelope)
    monkeypatch.setattr(sending, "_publish_when_ready", publish)
    event = cast(
        OutboxEvent,
        SimpleNamespace(tenant_id=uuid4(), payload={"evidence_version_id": str(uuid4())}),
    )
    await sending.on_review_decision(event)
    assert published == ([True] if publishes else [])
    assert len(written) == (1 if publishes else 0)
    if publishes:
        assert json.loads(str(written[0]["p"]))["paid_on"] == "2026-09-16"
