"""TASK-6960 (DEC-3960): a portal context's `mfa_at` is the time the portal session's own second
step verified (`auth_sessions.mfa_at`), never the trusted device's time and never the request's;
`portal_second_step` (DEC-1283) still says the floor was met either way."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from abacus.modules.identity import portal_session as ps
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import MembershipRecord
from abacus.modules.identity.service import portal_member_context

TENANT, USER, SESSION, MEMBERSHIP = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
STEPPED = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)
TOKEN = "pat_" + "a" * 43


def _wire(
    monkeypatch: pytest.MonkeyPatch, *, mfa_at: datetime | None, device: datetime | None
) -> None:
    row = SimpleNamespace(
        session_id=SESSION,
        user_id=USER,
        tenant_id=TENANT,
        mfa_at=mfa_at,
        device_trusted_at=device,
        access_expires_at=STEPPED + timedelta(minutes=15),
    )

    class Result:
        def first(self) -> object:
            return row

    class Conn:
        async def execute(self, *_a: object) -> Result:
            return Result()

    @asynccontextmanager
    async def transaction(_name: str) -> AsyncGenerator[Conn]:
        yield Conn()

    async def memberships(_u: uuid.UUID) -> list[MembershipRecord]:
        return [
            MembershipRecord(
                tenant_id=TENANT,
                membership_id=MEMBERSHIP,
                firm_role=None,
                firm_name="Brightwater Hale LLP",
                kind="client",
            )
        ]

    async def grants(*_a: object) -> list[object]:
        return [object()]

    async def floor(*_a: object) -> bool:
        return True

    def portal(_t: str) -> bool:
        return True

    monkeypatch.setattr(ps, "platform_transaction", transaction)
    monkeypatch.setattr(ps, "active_memberships", memberships)
    monkeypatch.setattr(ps, "active_grants", grants)
    monkeypatch.setattr(ps, "mfa_required", floor)
    monkeypatch.setattr(ps, "is_portal_token", portal)


async def _context() -> AuthContext:
    ctx = await ps.portal_context(TOKEN, "portal.example.test")
    assert ctx is not None
    return ctx


async def test_a_session_that_passed_the_second_step_carries_its_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, mfa_at=STEPPED, device=None)
    ctx = await _context()
    assert ctx.mfa_at == STEPPED
    assert ctx.portal_second_step and ctx.client and ctx.portal_session_id == SESSION


async def test_a_trusted_device_session_meets_the_floor_with_no_second_factor_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, mfa_at=None, device=STEPPED)
    ctx = await _context()
    assert ctx.mfa_at is None  # the device is the floor, not a second factor in this session
    assert ctx.portal_second_step


def test_the_context_builder_takes_the_time_only_by_name() -> None:
    membership = MembershipRecord(TENANT, MEMBERSHIP, None, "Brightwater Hale LLP", "client")
    plain = portal_member_context(USER, membership, SESSION)
    assert plain.mfa_at is None and not plain.portal_second_step
    stepped = portal_member_context(USER, membership, SESSION, second_step=True, mfa_at=STEPPED)
    assert stepped.mfa_at == STEPPED and stepped.firm_role is None and stepped.client
