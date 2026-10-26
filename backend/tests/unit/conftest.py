"""Unit tests have no database: `authorise` reads each firm's policy overrides and firm settings
(F-03-T24) from a stub with none, and an agent's initiator's access end (DEC-383) from a stub
that says it hasn't passed. Tests of overrides and settings replace it with their own. The
kill switches are stubbed for every suite but integration (`tests/conftest.py`)."""

from __future__ import annotations

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.repository import FirmPolicy


async def _no_policy(_: TenantContext) -> FirmPolicy:
    return FirmPolicy({}, frozenset())


async def _not_ended(*_: object) -> bool:
    return False


@pytest.fixture(autouse=True)
def _firm_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "firm_policy", _no_policy)
    monkeypatch.setattr(authz, "access_has_ended", _not_ended)
