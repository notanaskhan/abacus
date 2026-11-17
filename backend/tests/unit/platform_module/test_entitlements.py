"""F-03-T28 (ADR-148): "A route guarded by require_entitlement('attest') answers 403 for a firm
without it, and no ff.* module name remains in the flag registry"."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI

from abacus.api.app import (
    _domain_forbidden,  # pyright: ignore[reportPrivateUsage]  # the app's handler, mounted on a probe app
)
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainForbidden
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.platform import entitlements
from abacus.modules.platform.api import Entitlement, require_entitlement
from abacus_tools.codegen import feature_flags

TENANT = TenantContext(uuid.uuid4(), "human", "probe")


def _app(held: set[str], monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    async def found(_: TenantContext, module: str) -> Entitlement | None:
        return Entitlement(module, 46, 1000) if module in held else None

    app = FastAPI()
    app.add_exception_handler(DomainForbidden, _domain_forbidden)
    app.dependency_overrides[current_context] = lambda: AuthContext(
        TENANT, uuid.uuid4(), uuid.uuid4(), None, datetime.now(UTC)
    )

    @app.get("/attest-only")
    async def attest_only(
        held_: Annotated[Entitlement, Depends(require_entitlement("attest"))],
    ) -> dict[str, int | None]:
        return {"seats": held_.seats}

    monkeypatch.setattr(entitlements, "entitlement", found)
    return app


async def _get(app: FastAPI) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://probe"
    ) as client:
        return await client.get("/attest-only")


async def test_a_firm_without_attest_gets_403_naming_the_entitlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await _get(_app(set(), monkeypatch))
    assert response.status_code == 403
    assert response.json() == {"detail": "entitlement_required", "facts": {"module": "attest"}}


async def test_a_firm_with_attest_gets_through(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await _get(_app({"attest"}, monkeypatch))
    assert response.status_code == 200
    assert response.json() == {"seats": 46}


def test_an_unknown_module_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="unknown module"):
        require_entitlement("spaceships")  # type: ignore[arg-type]  # the point


@pytest.mark.parametrize("name", ["ff.attest", "ff.insights", "attest.workspace", "insights.home"])
def test_the_flag_registry_refuses_module_flags(name: str) -> None:
    source = (
        "flags:\n"
        f"  - name: {name}\n"
        "    description: probe\n"
        "    owner: probe\n"
        "    created: 2026-10-22\n"
        "    expires: 2026-12-22\n"
    )
    with pytest.raises(feature_flags.RegistryError, match="entitlement, not a flag"):
        feature_flags.parse(source)


def test_no_module_flag_remains_in_the_registry() -> None:
    names = [entry.name for entry in feature_flags.parse(feature_flags.source())]
    assert not [n for n in names if n.startswith("ff.") or n.split(".")[0] in entitlements.MODULES]
