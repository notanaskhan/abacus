"""P-10-T26 portal remainder (DEC-3170): a portal request notes its access token's expiry, so the
portal's streams close 30 seconds before it, like the firm app's (DEC-3141)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from abacus.kernel import request_context
from abacus.modules.identity import portal_session as ps

pytestmark = pytest.mark.asyncio
TENANT, USER, SESSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
EXPIRES = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


def _wire(monkeypatch: pytest.MonkeyPatch) -> None:
    row = SimpleNamespace(
        session_id=SESSION,
        user_id=USER,
        tenant_id=TENANT,
        mfa_at=EXPIRES,
        device_trusted_at=None,
        access_expires_at=EXPIRES,
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

    async def memberships(_u: uuid.UUID) -> list[object]:
        return [SimpleNamespace(tenant_id=TENANT, kind="client")]

    async def grants(*_a: object) -> list[object]:
        return [object()]

    def member(*_a: object, **_k: object) -> object:
        return SimpleNamespace(user_id=USER)

    monkeypatch.setattr(ps, "platform_transaction", transaction)
    monkeypatch.setattr(ps, "active_memberships", memberships)
    monkeypatch.setattr(ps, "active_grants", grants)
    monkeypatch.setattr(ps, "portal_member_context", member)


async def test_a_portal_request_notes_the_tokens_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch)
    token = "pat_" + "a" * 43

    def portal(_t: str) -> bool:
        return True

    monkeypatch.setattr(ps, "is_portal_token", portal)
    with request_context.bound(request_context.RequestContext()):
        assert await ps.portal_context(token, "portal.example.test") is not None
        assert request_context.token_expires_at() == EXPIRES


def test_the_resolver_answers_the_access_expiry() -> None:
    source = (
        Path(__file__).parents[3] / "migrations/versions/0762_portal_resolve_access_expiry.py"
    ).read_text()
    assert "s.access_expires_at" in source and "GRANT EXECUTE ON FUNCTION" in source
