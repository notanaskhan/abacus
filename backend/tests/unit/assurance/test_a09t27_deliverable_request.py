"""A-09-T27 rest (S48): a deliverable request emails the component auditor's engagement partner
the firm's `component_deliverable_request` template, as the requesting person, under the
request's own action; with no published template the send is recorded blocked."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date

import pytest

from abacus.modules.assurance import component_auditors as ca
from abacus.modules.communications import api as communications
from abacus.modules.communications.template_registry import SEND_AUTHORITIES


class _Tx:
    def __init__(self, sink: list[str]) -> None:
        self.sink = sink

    def record(self, action: str, **_: object) -> None:
        self.sink.append(action)


@pytest.mark.parametrize(
    ("status", "action"),
    [
        ("queued", "component_deliverable.request_sent"),
        ("blocked", "component_deliverable.request_blocked"),
    ],
)
async def test_the_request_is_sent_or_recorded_blocked(
    monkeypatch: pytest.MonkeyPatch, status: str, action: str
) -> None:
    sent: list[dict[str, object]] = []
    recorded: list[str] = []
    message = uuid.uuid4()

    async def send_templated(
        ctx: object, key: str, recipient: object, variables: object, **kw: object
    ) -> communications.SendOutcome:
        sent.append({"key": key, "variables": variables, **kw})
        return communications.SendOutcome(
            message,
            "queued" if status == "queued" else "blocked",
            None if status == "queued" else "template_missing",
        )

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        yield _Tx(recorded)

    class _Ctx:
        tenant = object()

    monkeypatch.setattr(communications, "send_templated", send_templated)
    monkeypatch.setattr(ca, "uow", uow)
    await ca._send_request(  # pyright: ignore[reportPrivateUsage] -- the private helper under test
        _Ctx(),  # type: ignore[arg-type] -- only the tenant is read
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "Pruett & Lang LLP",
        " Component reporting package ",
        date(2026, 12, 1),
        "key-1",
    )
    assert sent[0]["key"] == "component_deliverable_request"
    assert sent[0]["variables"] == {
        "organisation_name": "Pruett & Lang LLP",
        "deliverable_title": "Component reporting package",
        "due_date": "Tue Dec 1, 2026",
    }
    assert sent[0]["authority"] == "component_deliverable.manage"
    assert recorded == [action]


def test_the_send_authority_is_the_requests_own_action() -> None:
    assert ("component_deliverable_request", "component_deliverable.manage") in SEND_AUTHORITIES
