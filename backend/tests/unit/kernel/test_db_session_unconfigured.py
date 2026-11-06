"""TASK-5012 (DEC-2264): the application engine fails loudly when it has no URL."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from abacus.kernel.db import session


async def test_the_application_engine_needs_its_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "_engine", None)
    monkeypatch.setattr(session, "settings", lambda: SimpleNamespace(database_url=None))
    with pytest.raises(RuntimeError, match="database_url is not configured"):
        await session.ping()
