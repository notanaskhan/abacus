"""S33 CI fix: `signal_workflow` is best effort (N-04-T16). With no Temporal configured or none
reachable, a person's committed write still answers; nothing is raised."""

from __future__ import annotations

import pytest

from abacus.kernel import dispatch

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "error",
    [RuntimeError("temporal_target is not configured"), ConnectionRefusedError("refused")],
)
async def test_an_unavailable_service_skips_the_signal(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    async def down() -> object:
        raise error

    monkeypatch.setattr(dispatch, "temporal_client", down)
    await dispatch.signal_workflow("wf", "respond_by_changed", "2026-09-30")
