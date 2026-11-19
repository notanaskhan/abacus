"""C-02-T19 (TASK-8708; ADR-344 §3, §5; DEC-5705): the kill switch is read fresh (a flip refuses
the very next write) and fails closed when its state cannot be read; each W1 call's outcome maps to
the operation status its three write-once bodies are filed under."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from abacus.kernel import controls
from abacus.modules.adjustments import posting
from abacus.modules.integrations import writes
from abacus.modules.integrations.api import Posted


@pytest.mark.asyncio
async def test_ac_a_flip_refuses_the_next_write_without_waiting_for_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = uuid4()
    rows: list[Any] = [frozenset()]  # Any: the controls' active rows

    async def read() -> Any:  # noqa: ANN401 # Any: the controls' active rows
        return rows[0]

    monkeypatch.setattr(controls, "_read", read)
    ctx = SimpleNamespace(tenant_id=tenant)
    assert not await writes._ledger_write_paused(ctx)  # type: ignore[arg-type]  # a test literal
    rows[0] = frozenset({("ledger_write_pause", "firm", tenant, None)})
    assert await writes._ledger_write_paused(ctx)  # type: ignore[arg-type]  # a test literal


@pytest.mark.asyncio
async def test_ac_an_unreadable_switch_counts_as_on(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken() -> Any:  # noqa: ANN401 # Any: never returns
        raise RuntimeError("down")

    monkeypatch.setattr(controls, "_read", broken)
    assert await controls.control_active_now("ledger_write_pause", uuid4())


def test_ac_each_outcome_files_under_its_status() -> None:
    verified = posting._posted_evidence(Posted("48213", True))
    mismatch = posting._posted_evidence(Posted("48214", False))
    failed = posting._posted_evidence(Posted("", False, "inactive_account"))
    assert (verified.status, verified.external_ref) == ("verified", "48213")
    assert mismatch.status == "verify_mismatch"
    assert (failed.status, failed.external_ref) == ("failed", None)
    assert b"48213" in verified.response and b"true" in verified.readback
