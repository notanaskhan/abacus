"""A-07-T37 (TASK-6881): the archive lock is a manager's or EP's act on a fresh second factor.

Found by the Q-03-T234 catch-up read: `archive.lock`'s matrix row carries no `mfa_recent`, the
route's gate only authorises, and `decide_lock` stored `ctx.mfa_at or clock.system_now()`, so a
lock taken without a second factor was recorded as if one had been presented. `decide_lock` now
asks `fresh_mfa_at` first and stores the time the person presented.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.assurance import archive_lock as al
from abacus.modules.assurance.record_auth import RecordNeedsMfa
from abacus.modules.identity.api import AuthContext

pytestmark = pytest.mark.asyncio


def _ctx(mfa_minutes_ago: int | None) -> AuthContext:
    user = uuid4()
    return AuthContext(
        TenantContext(uuid4(), "human", str(user)),
        user,
        uuid4(),
        None,
        None if mfa_minutes_ago is None else system_now() - timedelta(minutes=mfa_minutes_ago),
    )


@pytest.mark.parametrize("mfa", [None, 24 * 60])
async def test_no_or_stale_second_factor_is_refused_before_anything_is_read(
    monkeypatch: pytest.MonkeyPatch, mfa: int | None
) -> None:
    read: list[object] = []

    async def state(*args: object) -> object:
        read.append(args)
        raise AssertionError("the archive was read before the second factor was checked")

    monkeypatch.setattr("abacus.modules.assurance.archive_gate.archive_state", state)
    with pytest.raises(RecordNeedsMfa):
        await al.decide_lock(
            _ctx(mfa), uuid4(), then_roll_forward=False, seen_checklist_hash="a" * 64
        )
    assert read == []


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_the_stored_time_is_never_the_clocks() -> None:
    source = Path(al.__file__).read_text(encoding="utf-8")
    assert "ctx.mfa_at or clock.system_now()" not in source
