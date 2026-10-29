"""One suite, two targets (ADR-044): the fake every pull request; the sandbox too when its
credentials are set (the nightly job, `-k sandbox`). Without them there is no sandbox case at all,
rather than a skipped one."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest

from abacus.kernel.clock import system_now

from . import targets


@pytest.fixture(params=["fake", *(["sandbox"] if targets.sandbox_configured() else [])])
async def target(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[targets.Target]:
    if request.param == "fake":
        yield targets.fake(tmp_path, expires_at=system_now() + timedelta(hours=1))
        return
    made = targets.sandbox()
    yield made
    close = getattr(made.transport.inner, "close", None)
    if close is not None:
        await close()
