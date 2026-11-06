"""A-04-T29 (AC4.8; DEC-2327): the re-draft after Internal Control. The start itself is stubbed:
this pins when it happens and for whom; the drafter's own suite covers the run."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

import abacus.api as app_package  # loading it loads every module
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.modules.agents.api import followed_up_running
from abacus.modules.agents.section_draft import (
    _source_event as source_event,  # pyright: ignore[reportPrivateUsage] -- the key the run was started under
)
from abacus.modules.assurance import ic_redraft
from abacus.modules.assurance.ic_mode import MODE as IC_MODE

from .support import Firm, Seeder, make_firm

pytestmark = pytest.mark.asyncio


def _event(firm: Firm, mode: str = "ic", run: uuid.UUID | None = None) -> OutboxEvent:
    return cast(
        OutboxEvent,
        SimpleNamespace(
            tenant_id=firm.tenant_id,
            payload={
                "mode": mode,
                "run_id": str(run or uuid.uuid4()),
                "engagement_id": str(firm.engagement_id),
                "workpaper_id": str(uuid.uuid4()),
                "initiator_user_id": str(firm.user_id),
            },
        ),
    )


async def _link_risk(firm: Firm, target: str = "AUD-09") -> None:
    work_item = await firm.seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "SELECT $1, $2, client_id, 'notice', 'Audit', $3 FROM engagements WHERE id = $2 "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    risk = await firm.seed.id(
        "INSERT INTO risk_register_rows (tenant_id, engagement_id, work_item_id, code, level, "
        "area_key, area_label, inherent_risk, control_risk, rmm, fraud, content_hash) VALUES "
        "($1, $2, $3, 'R3', 'financial_statement', 'revenue', 'Revenue', 'high', 'max', 'high', "
        "'none', $4) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        "a" * 64,
    )
    await firm.seed.run(
        "INSERT INTO risk_linkages (tenant_id, engagement_id, work_item_id, risk_id, target_kind, "
        "target_ref, state) VALUES ($1, $2, $3, $4, 'workpaper', $5, 'linked')",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        risk,
        target,
    )


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    async def start(
        _ctx: object, _e: object, _paper: object, mode: str, _s: object, key: str
    ) -> object:
        calls.append((mode, key))
        return uuid.uuid4()

    async def paper(_ctx: object, _e: object, _kind: str) -> object:
        return uuid.uuid4()

    async def member(tenant_id: uuid.UUID, user_id: uuid.UUID) -> object:
        return SimpleNamespace(tenant_id=tenant_id, user_id=user_id)

    async def on(_tenant: TenantContext, _flag: object) -> bool:
        return True

    monkeypatch.setattr(ic_redraft, "start_section_draft", start)
    monkeypatch.setattr(ic_redraft, "member_context", member)
    monkeypatch.setattr(ic_redraft, "flag_enabled", on)
    monkeypatch.setattr("abacus.modules.workpapers.api.paper_of_kind", paper)
    return calls


async def test_ac_a_finished_ic_run_with_a_linked_risk_starts_one_risk_run(
    seed: Seeder, started: list[tuple[str, str]]
) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    await _link_risk(firm)
    run = uuid.uuid4()
    await ic_redraft.on_section_draft_finished(_event(firm, run=run))
    assert started == [("risk", f"ic_redraft:{run}")]


async def test_ac_no_linked_risk_starts_nothing(
    seed: Seeder, started: list[tuple[str, str]]
) -> None:
    firm = await make_firm(seed)
    await ic_redraft.on_section_draft_finished(_event(firm))
    assert started == []


async def test_ac_a_link_to_another_paper_starts_nothing(
    seed: Seeder, started: list[tuple[str, str]]
) -> None:
    firm = await make_firm(seed)
    await _link_risk(firm, "AUD-10")
    await ic_redraft.on_section_draft_finished(_event(firm))
    assert started == []


async def test_ac_another_mode_starts_nothing(
    seed: Seeder, started: list[tuple[str, str]]
) -> None:
    firm = await make_firm(seed)
    await _link_risk(firm)
    await ic_redraft.on_section_draft_finished(_event(firm, mode="risk"))
    assert started == []


@pytest.mark.parametrize("change", ["flag_off", "no_person"])
async def test_ac_the_flag_off_or_no_person_starts_nothing(
    seed: Seeder,
    started: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    firm = await make_firm(seed)
    await _link_risk(firm)

    async def none(*_a: object) -> object:
        return None

    async def off(*_a: object) -> bool:
        return False

    swap: dict[str, tuple[str, object]] = {
        "flag_off": ("flag_enabled", off),
        "no_person": ("member_context", none),
    }
    name, replacement = swap[change]
    monkeypatch.setattr(ic_redraft, name, replacement)
    await ic_redraft.on_section_draft_finished(_event(firm))
    assert started == []


async def _run(
    firm: Firm, status: str, *, output: str | None, event: uuid.UUID | None
) -> uuid.UUID:
    return await firm.seed.id(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, source_event_id, task_scope, status, output, finished_at) VALUES "
        "($1, 'workpapers.section_drafter', 1, $2, $3, $4, '{}', $5, $6::jsonb, "
        "CASE WHEN $5::text = 'running' THEN NULL ELSE clock_timestamp() END) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
        event,
        status,
        output,
    )


async def test_ac_revising_reads_the_run_started_after_the_latest_ic_run(seed: Seeder) -> None:
    firm = await make_firm(seed)
    paper = uuid.uuid4()

    async def revising() -> bool:
        return await followed_up_running(
            firm.tenant_id, firm.engagement_id, IC_MODE, paper, ic_redraft.KEY_PREFIX
        )

    assert await revising() is False
    ic = await _run(firm, "completed", output='{"mode": "ic"}', event=None)
    assert await revising() is False
    event = source_event(firm.tenant_id, paper, None, f"{ic_redraft.KEY_PREFIX}:{ic}")
    run = await _run(firm, "running", output=None, event=event)
    assert await revising() is True
    await seed.run(
        "UPDATE agent_runs SET status = 'completed', finished_at = clock_timestamp() "
        "WHERE id = $1",
        run,
    )
    assert await revising() is False
