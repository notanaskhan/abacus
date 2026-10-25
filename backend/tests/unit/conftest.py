"""Unit tests have no database: `authorise` reads each firm's policy overrides and firm settings
(F-03-T24) from a stub with none, and the kill switches (Q-01-T36, T37) from a stub with none on.
Tests of overrides, settings and switches replace them with their own."""

from __future__ import annotations

import pytest

from abacus.kernel import controls
from abacus.kernel.controls import Active
from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.repository import FirmPolicy


async def _no_policy(_: TenantContext) -> FirmPolicy:
    return FirmPolicy({}, frozenset())


@pytest.fixture(autouse=True)
def _firm_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "firm_policy", _no_policy)


async def _no_switches() -> Active:
    return frozenset()


@pytest.fixture(autouse=True)
def _no_kill_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without it, an unreadable state fails closed: every write would answer `read_only`."""
    controls.forget_controls()
    monkeypatch.setattr(controls, "_read", _no_switches)
