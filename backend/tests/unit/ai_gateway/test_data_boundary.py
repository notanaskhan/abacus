"""SPEC-026 AC-2 (TASK-049): before any network call on a real route, the call's firm must be
synthetic; otherwise the call is refused, audited and counted, and the provider never runs."""

from __future__ import annotations

import ast
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from abacus.ai_gateway import boundary
from abacus.ai_gateway.boundary import DataBoundaryRefused, enforce_boundary
from abacus.kernel.db import TenantContext

GATEWAY = Path(boundary.__file__).with_name("__init__.py")


class _Tx:
    def __init__(self, records: list[str]) -> None:
        self.records = records

    def record(self, action: str, **_: object) -> None:
        self.records.append(action)


@pytest.fixture
def audited(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    records: list[str] = []

    @asynccontextmanager
    async def fake_uow(tenant: object) -> AsyncGenerator[_Tx]:
        yield _Tx(records)

    monkeypatch.setattr(boundary, "uow", fake_uow)
    monkeypatch.setattr(boundary, "_check", None)
    boundary.clear_cache()
    return records


def _tenant() -> TenantContext:
    return TenantContext(uuid.uuid4(), "system", "test")


def _register(monkeypatch: pytest.MonkeyPatch, answer: bool, asked: list[object]) -> None:
    async def check(tenant: TenantContext) -> bool:
        asked.append(tenant.tenant_id)
        return answer

    monkeypatch.setattr(boundary, "_check", check)


async def test_ac2_the_fake_route_needs_no_check(audited: list[str]) -> None:
    await enforce_boundary(_tenant(), "fake", "evidence.screen@v0")
    assert audited == []


async def test_ac2_unregistered_means_refused(audited: list[str]) -> None:
    with pytest.raises(DataBoundaryRefused):
        await enforce_boundary(_tenant(), "direct", "evidence.screen@v0")
    assert audited == ["ai.boundary_refused"]


@pytest.mark.parametrize("route", ["direct", "bedrock"])
async def test_ac2_a_firm_that_isnt_synthetic_is_refused_and_audited(
    audited: list[str], monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    _register(monkeypatch, False, [])
    with pytest.raises(DataBoundaryRefused):
        await enforce_boundary(_tenant(), route, "evidence.screen@v0")  # pyright: ignore[reportArgumentType] -- a real route
    assert audited == ["ai.boundary_refused"]


async def test_ac2_a_synthetic_firm_passes_and_the_answer_is_cached(
    audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[object] = []
    _register(monkeypatch, True, asked)
    tenant = _tenant()
    await enforce_boundary(tenant, "direct", "evidence.screen@v0")
    await enforce_boundary(tenant, "direct", "evidence.screen@v0")
    assert asked == [tenant.tenant_id] and audited == []


def test_ac2_the_refusal_is_not_a_provider_error() -> None:
    """Never retried or handed to another route (the gateway retries `ProviderError` only)."""
    from abacus.ai_gateway import ProviderError

    assert not issubclass(DataBoundaryRefused, ProviderError)


def test_ac2_every_provider_call_in_the_gateway_is_preceded_by_the_boundary() -> None:
    """The gateway's only two model calls (`.complete`, `.embed`) each follow `enforce_boundary`
    in the same block, so no path reaches a provider unchecked."""
    tree = ast.parse(GATEWAY.read_text())
    calls = 0
    for node in ast.walk(tree):
        body: object = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        statements = [s for s in cast(list[object], body) if isinstance(s, ast.stmt)]
        for i, statement in enumerate(statements):
            source = ast.unparse(statement)
            direct = isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign))
            if direct and (".complete(" in source or "embedder().embed(" in source):
                calls += 1
                before = " ".join(ast.unparse(s) for s in statements[:i])
                assert "enforce_boundary(" in before, source
    assert calls == 2
