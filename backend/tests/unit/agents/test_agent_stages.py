"""SPEC-036 AC-5 (TASK-076, TASK-089): a cleared agent is off for a real firm until set to
shadow; synthetic firms never run in shadow; the founder's command refuses `live` before the
shadow threshold (Q1)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import stages
from abacus_tools import agent_stage
from abacus_tools.agent_stage import ShadowReport, StageRefused, set_stage

TENANT = TenantContext(uuid.uuid4(), "system", "test")


@pytest.fixture
def row(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    found: dict[str, object] = {"stage": None, "synthetic": False, "cleared": True}

    async def stage_of(session: object, agent_id: str) -> object:
        return found["stage"]

    async def is_synthetic(tenant: object) -> bool:
        return bool(found["synthetic"])

    @asynccontextmanager
    async def session(tenant: object) -> AsyncGenerator[None]:
        yield None

    monkeypatch.setattr(stages, "stage_of", stage_of)
    monkeypatch.setattr(stages, "is_synthetic", is_synthetic)
    monkeypatch.setattr(stages, "tenant_session", session)

    def cleared(agent: str) -> bool:
        return bool(found["cleared"])

    monkeypatch.setattr(stages, "cleared_for_client_data", cleared)
    return found


async def test_ac5_a_cleared_agent_is_off_until_set(row: dict[str, object]) -> None:
    assert await stages.stage_for(TENANT, "evidence.screener") is None  # the gateway refuses
    assert not await stages.starts_in_shadow(None, TENANT, "evidence.screener")  # type: ignore[arg-type] -- the session is faked


async def test_ac5_an_agent_set_to_shadow_runs_in_shadow(row: dict[str, object]) -> None:
    row["stage"] = "shadow"
    assert await stages.stage_for(TENANT, "evidence.screener") == "shadow"
    assert await stages.starts_in_shadow(None, TENANT, "evidence.screener")  # type: ignore[arg-type] -- as above


async def test_ac5_an_uncleared_agent_has_no_stage(row: dict[str, object]) -> None:
    row["cleared"] = False
    assert await stages.stage_for(TENANT, "evidence.screener") is None


async def test_ac5_a_promoted_agent_runs_live(row: dict[str, object]) -> None:
    row["stage"] = "live"
    assert await stages.stage_for(TENANT, "evidence.screener") == "live"
    assert not await stages.starts_in_shadow(None, TENANT, "evidence.screener")  # type: ignore[arg-type] -- as above


async def test_ac5_synthetic_firms_never_run_in_shadow(row: dict[str, object]) -> None:
    row["synthetic"] = True
    assert not await stages.starts_in_shadow(None, TENANT, "evidence.screener")  # type: ignore[arg-type] -- as above


def _report(runs: int, days: int) -> ShadowReport:
    first = datetime.now(UTC) - timedelta(days=days)
    return ShadowReport(runs, first, {"completed": runs}, Decimal("1.5"), 10, 9)


@pytest.mark.parametrize(("runs", "days"), [(49, 30), (80, 13)])
async def test_q1_live_is_refused_before_the_shadow_threshold(
    monkeypatch: pytest.MonkeyPatch, runs: int, days: int
) -> None:
    async def report(firm: uuid.UUID, agent_id: str) -> ShadowReport:
        return _report(runs, days)

    monkeypatch.setattr(agent_stage, "report", report)
    with pytest.raises(StageRefused, match="shadow runs"):
        await set_stage(uuid.uuid4(), "evidence.screener", "live", "compared, looks good")


async def test_d1_a_note_and_a_known_stage_are_required() -> None:
    with pytest.raises(StageRefused):
        await set_stage(uuid.uuid4(), "evidence.screener", "on", "x")
    with pytest.raises(StageRefused):
        await set_stage(uuid.uuid4(), "evidence.screener", "off", "  ")


def test_q1_the_report_knows_when_it_is_ready() -> None:
    assert _report(50, 14).ready
    assert not _report(50, 13).ready
