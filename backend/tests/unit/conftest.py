"""Unit tests have no database: `authorise` reads each firm's policy overrides and firm settings
(F-03-T24) from a stub with none. Tests of overrides and settings replace it with their own."""

from __future__ import annotations

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.repository import FirmPolicy


async def _no_policy(_: TenantContext) -> FirmPolicy:
    return FirmPolicy({}, frozenset())


@pytest.fixture(autouse=True)
def _firm_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "firm_policy", _no_policy)
