"""One registered domain serves the firm app, the portal and mail (DEC-3901): no firm's portal
host may take a platform label under it, nor the domain itself."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.kernel.uow import UnitOfWork
from abacus.modules.portal import branding

BASE = "portal-example.test"


@pytest.mark.parametrize("label", ["app", "connect", "notify", "mail", "bounce", "www", "staging"])
def test_platform_labels_are_reserved(label: str) -> None:
    assert branding.reserved_host(f"{label}.{BASE}", BASE)


def test_the_domain_itself_is_reserved() -> None:
    assert branding.reserved_host(BASE, BASE)


@pytest.mark.parametrize(
    "host", [f"brightwaterhale.{BASE}", f"app.firm.{BASE}", "app.other-example.test"]
)
def test_firm_hosts_are_not_reserved(host: str) -> None:
    assert not branding.reserved_host(host, BASE)


def test_nothing_is_reserved_without_a_portal_domain() -> None:
    assert not branding.reserved_host(f"app.{BASE}", None)


async def test_add_portal_host_refuses_a_reserved_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(branding, "settings", lambda: SimpleNamespace(portal_base_domain=BASE))
    with pytest.raises(branding.HostInvalid):
        await branding.add_portal_host(cast(UnitOfWork, None), uuid4(), f"App.{BASE}", "default")
